import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Path,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session
import jwt

from app.db.session import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.chat_repository import ChatRepository
from app.services.chat_service import ChatService
from app.websockets.manager import ws_manager
from app.schemas.chat import (
    CreateChatRequest,
    ChatResponse,
    MessagesListResponse,
    MessageSummary,
    SendMessageRequest,
    EditMessageRequest,
    DeleteMessageRequest,
    ReactionRequest,
)

router = APIRouter(tags=["Chats"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_participant_ids(db: Session, conv_id_str: str) -> List[str]:
    try:
        conv_uuid = uuid.UUID(conv_id_str)
        conv = ChatRepository(db).get_conversation_by_id(conv_uuid)
        if conv and conv.participants:
            return [str(p.user_id) for p in conv.participants]
    except Exception:
        pass
    return []


# -------------------------------------------------------------
# REST ENDPOINTS
# -------------------------------------------------------------

@router.post(
    "/chats",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or retrieve direct one-to-one conversation",
)
def create_or_get_chat(
    data: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return service.get_or_create_chat(
        current_user=current_user,
        participant_user_id_str=data.participant_user_id,
    )


@router.get(
    "/chats",
    response_model=List[ChatResponse],
    status_code=status.HTTP_200_OK,
    summary="List all conversations for the authenticated user",
)
def list_chats(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return service.list_chats(current_user)


@router.get(
    "/chats/{conversation_id}/messages",
    response_model=MessagesListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get paginated message history for a conversation",
)
def get_messages(
    conversation_id: str = Path(..., description="UUID of conversation"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return service.get_messages(
        current_user=current_user,
        conversation_id_str=conversation_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/chats/{conversation_id}/messages",
    response_model=MessageSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message (text or voice note) via REST",
)
async def send_message_rest(
    conversation_id: str = Path(..., description="UUID of conversation"),
    data: SendMessageRequest = ...,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    message_summary = service.save_message(
        current_user=current_user,
        conversation_id_str=conversation_id,
        content=data.content or "",
        message_type=data.message_type or "text",
        media_url=data.media_url,
        media_duration=data.media_duration,
    )

    participant_ids = get_participant_ids(db, conversation_id)

    payload = {
        "type": "new_message",
        "message": {
            "id": message_summary.id,
            "conversation_id": message_summary.conversation_id,
            "sender_id": message_summary.sender_id,
            "sender_name": message_summary.sender_name,
            "content": message_summary.content,
            "message_type": message_summary.message_type,
            "media_url": message_summary.media_url,
            "media_duration": message_summary.media_duration,
            "reactions": message_summary.reactions,
            "is_deleted_everyone": message_summary.is_deleted_everyone,
            "deleted_by_users": message_summary.deleted_by_users,
            "is_edited": message_summary.is_edited,
            "edited_at": message_summary.edited_at.isoformat() if message_summary.edited_at else None,
            "created_at": message_summary.created_at.isoformat(),
            "is_read": message_summary.is_read,
        },
    }
    await ws_manager.broadcast_to_conversation(
        conversation_id,
        payload,
        participant_user_ids=participant_ids,
    )

    return message_summary


@router.patch(
    "/chats/{conversation_id}/messages/{message_id}",
    response_model=MessageSummary,
    status_code=status.HTTP_200_OK,
    summary="Edit an existing message",
)
async def edit_message_endpoint(
    conversation_id: str = Path(...),
    message_id: str = Path(...),
    data: EditMessageRequest = ...,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    updated = service.edit_message(
        current_user=current_user,
        conversation_id_str=conversation_id,
        message_id_str=message_id,
        new_content=data.content,
    )
    participant_ids = get_participant_ids(db, conversation_id)
    await ws_manager.broadcast_to_conversation(
        conversation_id,
        {
            "type": "message_edited",
            "conversation_id": conversation_id,
            "message_id": updated.id,
            "content": updated.content,
            "is_edited": updated.is_edited,
            "edited_at": updated.edited_at.isoformat() if updated.edited_at else None,
        },
        participant_user_ids=participant_ids,
    )
    return updated


@router.delete(
    "/chats/{conversation_id}/messages/{message_id}",
    response_model=MessageSummary,
    status_code=status.HTTP_200_OK,
    summary="Delete a message (everyone or for me)",
)
async def delete_message_endpoint(
    conversation_id: str = Path(...),
    message_id: str = Path(...),
    data: DeleteMessageRequest = ...,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    updated = service.delete_message(
        current_user=current_user,
        conversation_id_str=conversation_id,
        message_id_str=message_id,
        delete_type=data.delete_type,
    )
    participant_ids = get_participant_ids(db, conversation_id)
    await ws_manager.broadcast_to_conversation(
        conversation_id,
        {
            "type": "message_deleted",
            "conversation_id": conversation_id,
            "message_id": updated.id,
            "delete_type": data.delete_type,
            "deleted_by_user_id": str(current_user.id),
            "is_deleted_everyone": updated.is_deleted_everyone,
            "deleted_by_users": updated.deleted_by_users,
            "content": updated.content,
        },
        participant_user_ids=participant_ids,
    )
    return updated


@router.post(
    "/chats/{conversation_id}/messages/{message_id}/reactions",
    response_model=MessageSummary,
    status_code=status.HTTP_200_OK,
    summary="Toggle emoji reaction on a message",
)
async def reaction_endpoint(
    conversation_id: str = Path(...),
    message_id: str = Path(...),
    data: ReactionRequest = ...,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    updated = service.toggle_reaction(
        current_user=current_user,
        conversation_id_str=conversation_id,
        message_id_str=message_id,
        emoji=data.emoji,
    )
    participant_ids = get_participant_ids(db, conversation_id)
    await ws_manager.broadcast_to_conversation(
        conversation_id,
        {
            "type": "message_reaction",
            "conversation_id": conversation_id,
            "message_id": updated.id,
            "reactions": updated.reactions,
        },
        participant_user_ids=participant_ids,
    )
    return updated


@router.post(
    "/chats/{conversation_id}/read",
    status_code=status.HTTP_200_OK,
    summary="Mark messages as read in conversation",
)
async def mark_messages_read_endpoint(
    conversation_id: str = Path(..., description="UUID of conversation"),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    count = service.mark_messages_read(current_user, conversation_id)
    if count > 0:
        participant_ids = get_participant_ids(db, conversation_id)
        await ws_manager.broadcast_to_conversation(
            conversation_id,
            {
                "type": "messages_read",
                "conversation_id": conversation_id,
                "reader_id": str(current_user.id),
            },
            participant_user_ids=participant_ids,
        )
    return {"status": "ok", "marked_read": count}


# -------------------------------------------------------------
# WEBSOCKET REAL-TIME ENDPOINTS
# -------------------------------------------------------------

def authenticate_ws_connection(websocket: WebSocket, db: Session) -> Optional[User]:
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get("access_token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except Exception:
        return None

    jti = payload.get("jti")
    if jti and TokenRepository(db).is_token_revoked(jti):
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None

    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active or not user.is_verified:
        return None

    return user


@router.websocket("/ws/chats/{conversation_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
):
    db: Session = SessionLocal()
    user: Optional[User] = None
    try:
        user = authenticate_ws_connection(websocket, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        chat_repo = ChatRepository(db)
        if not chat_repo.is_user_participant(conv_uuid, user.id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await ws_manager.connect(
            conversation_id=conversation_id,
            user_id=str(user.id),
            websocket=websocket,
        )

        # Broadcast that user is online
        await ws_manager.broadcast_user_status(str(user.id), is_online=True)

        await websocket.send_json({
            "type": "connection_established",
            "conversation_id": conversation_id,
            "user_id": str(user.id),
        })

        chat_service = ChatService(db)
        participant_ids = get_participant_ids(db, conversation_id)

        # Mark any unread messages as read upon connection
        marked = chat_service.mark_messages_read(user, conversation_id)
        if marked > 0:
            await ws_manager.broadcast_to_conversation(
                conversation_id,
                {
                    "type": "messages_read",
                    "conversation_id": conversation_id,
                    "reader_id": str(user.id),
                },
                participant_user_ids=participant_ids,
            )

        # Message listening loop
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            # 1. Ping
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # 2. Typing indicator
            if msg_type == "typing":
                is_typing = bool(data.get("is_typing", False))
                await ws_manager.broadcast_to_conversation(
                    conversation_id,
                    {
                        "type": "typing",
                        "conversation_id": conversation_id,
                        "user_id": str(user.id),
                        "user_name": user.full_name,
                        "is_typing": is_typing,
                    },
                    participant_user_ids=participant_ids,
                )
                continue

            # 3. Mark read
            if msg_type == "mark_read":
                marked_count = chat_service.mark_messages_read(user, conversation_id)
                if marked_count > 0:
                    await ws_manager.broadcast_to_conversation(
                        conversation_id,
                        {
                            "type": "messages_read",
                            "conversation_id": conversation_id,
                            "reader_id": str(user.id),
                        },
                        participant_user_ids=participant_ids,
                    )
                continue

            # 4. Reaction toggle
            if msg_type == "reaction":
                m_id = data.get("message_id")
                emoji = data.get("emoji")
                if m_id and emoji:
                    try:
                        updated_msg = chat_service.toggle_reaction(user, conversation_id, m_id, emoji)
                        await ws_manager.broadcast_to_conversation(
                            conversation_id,
                            {
                                "type": "message_reaction",
                                "conversation_id": conversation_id,
                                "message_id": updated_msg.id,
                                "reactions": updated_msg.reactions,
                            },
                            participant_user_ids=participant_ids,
                        )
                    except Exception as ex:
                        print("Reaction error:", ex)
                continue

            # 5. Edit message
            if msg_type == "edit_message":
                m_id = data.get("message_id")
                new_text = (data.get("content") or "").strip()
                if m_id and new_text:
                    try:
                        edited_msg = chat_service.edit_message(user, conversation_id, m_id, new_text)
                        await ws_manager.broadcast_to_conversation(
                            conversation_id,
                            {
                                "type": "message_edited",
                                "conversation_id": conversation_id,
                                "message_id": edited_msg.id,
                                "content": edited_msg.content,
                                "is_edited": edited_msg.is_edited,
                                "edited_at": edited_msg.edited_at.isoformat() if edited_msg.edited_at else None,
                            },
                            participant_user_ids=participant_ids,
                        )
                    except Exception as ex:
                        print("Edit error:", ex)
                continue

            # 6. Delete message
            if msg_type == "delete_message":
                m_id = data.get("message_id")
                del_type = data.get("delete_type", "everyone")
                if m_id:
                    try:
                        deleted_msg = chat_service.delete_message(user, conversation_id, m_id, del_type)
                        await ws_manager.broadcast_to_conversation(
                            conversation_id,
                            {
                                "type": "message_deleted",
                                "conversation_id": conversation_id,
                                "message_id": deleted_msg.id,
                                "delete_type": del_type,
                                "deleted_by_user_id": str(user.id),
                                "is_deleted_everyone": deleted_msg.is_deleted_everyone,
                                "deleted_by_users": deleted_msg.deleted_by_users,
                                "content": deleted_msg.content,
                            },
                            participant_user_ids=participant_ids,
                        )
                    except Exception as ex:
                        print("Delete error:", ex)
                continue

            # 7. New message (text or voice note)
            content = (data.get("content") or "").strip()
            message_type = data.get("message_type", "text")
            media_url = data.get("media_url")
            media_duration = data.get("media_duration")

            if not content and not media_url:
                continue

            if len(content) > 4000:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message exceeds maximum length of 4000 characters.",
                })
                continue

            saved_msg = chat_service.save_message(
                current_user=user,
                conversation_id_str=conversation_id,
                content=content,
                message_type=message_type,
                media_url=media_url,
                media_duration=media_duration,
            )

            broadcast_payload = {
                "type": "new_message",
                "message": {
                    "id": saved_msg.id,
                    "conversation_id": saved_msg.conversation_id,
                    "sender_id": saved_msg.sender_id,
                    "sender_name": saved_msg.sender_name,
                    "content": saved_msg.content,
                    "message_type": saved_msg.message_type,
                    "media_url": saved_msg.media_url,
                    "media_duration": saved_msg.media_duration,
                    "reactions": saved_msg.reactions,
                    "is_deleted_everyone": saved_msg.is_deleted_everyone,
                    "deleted_by_users": saved_msg.deleted_by_users,
                    "is_edited": saved_msg.is_edited,
                    "edited_at": saved_msg.edited_at.isoformat() if saved_msg.edited_at else None,
                    "created_at": saved_msg.created_at.isoformat(),
                    "is_read": saved_msg.is_read,
                },
            }
            await ws_manager.broadcast_to_conversation(
                conversation_id,
                broadcast_payload,
                participant_user_ids=participant_ids,
            )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error in {conversation_id}: {e}")
    finally:
        if user:
            ws_manager.disconnect(
                conversation_id=conversation_id,
                user_id=str(user.id),
                websocket=websocket,
            )
            # If user has no more open sockets, update last_seen_at & broadcast offline
            if not ws_manager.is_user_online(str(user.id)):
                now = datetime.now(timezone.utc)
                user.last_seen_at = now
                try:
                    db.commit()
                except Exception:
                    pass
                await ws_manager.broadcast_user_status(str(user.id), is_online=False, last_seen_at=now.isoformat())
        db.close()


@router.websocket("/ws/user")
async def user_notifications_websocket_endpoint(websocket: WebSocket):
    db: Session = SessionLocal()
    user: Optional[User] = None
    try:
        user = authenticate_ws_connection(websocket, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await ws_manager.connect_user(user_id=str(user.id), websocket=websocket)
        await ws_manager.broadcast_user_status(str(user.id), is_online=True)

        await websocket.send_json({
            "type": "user_stream_established",
            "user_id": str(user.id),
        })

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if user:
            ws_manager.disconnect_user(user_id=str(user.id), websocket=websocket)
            if not ws_manager.is_user_online(str(user.id)):
                now = datetime.now(timezone.utc)
                user.last_seen_at = now
                try:
                    db.commit()
                except Exception:
                    pass
                await ws_manager.broadcast_user_status(str(user.id), is_online=False, last_seen_at=now.isoformat())
        db.close()

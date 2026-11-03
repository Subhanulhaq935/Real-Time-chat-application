import uuid
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
)

router = APIRouter(tags=["Chats"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


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
    limit: int = Query(50, ge=1, le=100),
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


def get_participant_ids(db: Session, conv_id_str: str) -> List[str]:
    try:
        conv_uuid = uuid.UUID(conv_id_str)
        conv = ChatRepository(db).get_conversation_by_id(conv_uuid)
        if conv and conv.participants:
            return [str(p.user_id) for p in conv.participants]
    except Exception:
        pass
    return []


@router.post(
    "/chats/{conversation_id}/messages",
    response_model=MessageSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message via REST (also broadcasts over WebSocket)",
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
        content=data.content,
    )

    participant_ids = get_participant_ids(db, conversation_id)

    # Broadcast new message to all active WebSocket listeners (room + user sidebar streams)
    payload = {
        "type": "new_message",
        "message": {
            "id": message_summary.id,
            "conversation_id": message_summary.conversation_id,
            "sender_id": message_summary.sender_id,
            "sender_name": message_summary.sender_name,
            "content": message_summary.content,
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
# WEBSOCKET REAL-TIME ENDPOINT
# -------------------------------------------------------------

def authenticate_ws_connection(websocket: WebSocket, db: Session) -> Optional[User]:
    """Authenticates WebSocket handshake using query param, cookie, or header."""
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
    try:
        # 1. Authenticate user
        user = authenticate_ws_connection(websocket, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 2. Verify conversation membership
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        chat_repo = ChatRepository(db)
        if not chat_repo.is_user_participant(conv_uuid, user.id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 3. Accept connection and register with ws_manager
        await ws_manager.connect(
            conversation_id=conversation_id,
            user_id=str(user.id),
            websocket=websocket,
        )

        # Notify connection success to client
        await websocket.send_json({
            "type": "connection_established",
            "conversation_id": conversation_id,
            "user_id": str(user.id),
        })

        chat_service = ChatService(db)
        participant_ids = get_participant_ids(db, conversation_id)

        # Mark any existing unread messages as read upon connection
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

        # 4. Message listening loop
        while True:
            data = await websocket.receive_json()

            # Handle ping / keepalive
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # Handle mark_read request from client
            if data.get("type") == "mark_read":
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

            content = data.get("content", "").strip()
            if not content:
                continue

            if len(content) > 4000:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message exceeds maximum length of 4000 characters.",
                })
                continue

            # Save to PostgreSQL FIRST
            saved_msg = chat_service.save_message(
                current_user=user,
                conversation_id_str=conversation_id,
                content=content,
            )

            # Broadcast to all connected participants in the conversation (room + user streams)
            broadcast_payload = {
                "type": "new_message",
                "message": {
                    "id": saved_msg.id,
                    "conversation_id": saved_msg.conversation_id,
                    "sender_id": saved_msg.sender_id,
                    "sender_name": saved_msg.sender_name,
                    "content": saved_msg.content,
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
        if 'user' in locals() and user:
            ws_manager.disconnect(
                conversation_id=conversation_id,
                user_id=str(user.id),
                websocket=websocket,
            )
        db.close()


@router.websocket("/ws/user")
async def user_notifications_websocket_endpoint(websocket: WebSocket):
    """
    User-level real-time stream so the sidebar conversation list, message previews,
    and unread badges update instantly even when no chat is currently selected.
    """
    db: Session = SessionLocal()
    try:
        user = authenticate_ws_connection(websocket, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await ws_manager.connect_user(user_id=str(user.id), websocket=websocket)
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
        if 'user' in locals() and user:
            ws_manager.disconnect_user(user_id=str(user.id), websocket=websocket)
        db.close()


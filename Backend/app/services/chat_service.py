import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import (
    ParticipantSummary,
    MessageSummary,
    ChatResponse,
    MessagesListResponse,
)
from app.websockets.manager import ws_manager


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.contact_repo = ContactRepository(db)
        self.chat_repo = ChatRepository(db)

    def _resolve_participant_summary(
        self,
        current_user: User,
        target_user: User,
    ) -> ParticipantSummary:
        """Resolves target user details incorporating any private custom alias set by current_user."""
        contact = self.contact_repo.get_contact(current_user.id, target_user.id)
        custom_name = contact.custom_name if contact else None
        display_name = custom_name if custom_name else target_user.full_name

        is_online = ws_manager.is_user_online(str(target_user.id))

        return ParticipantSummary(
            id=str(target_user.id),
            email=target_user.email,
            original_name=target_user.full_name,
            display_name=display_name,
            is_online=is_online,
            last_seen_at=target_user.last_seen_at,
        )

    def _build_message_summary(self, message, current_user_id: uuid.UUID, sender_name: Optional[str] = None) -> MessageSummary:
        is_mine = str(message.sender_id) == str(current_user_id)
        s_name = sender_name or (message.sender.full_name if getattr(message, "sender", None) else "User")
        return MessageSummary(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            sender_id=str(message.sender_id),
            sender_name=s_name,
            content=message.content,
            message_type=message.message_type or "text",
            media_url=message.media_url,
            media_duration=message.media_duration,
            reactions=message.reactions or [],
            is_deleted_everyone=message.is_deleted_everyone,
            deleted_by_users=message.deleted_by_users or [],
            is_edited=message.is_edited,
            edited_at=message.edited_at,
            created_at=message.created_at,
            is_mine=is_mine,
            is_read=message.is_read,
        )

    def get_or_create_chat(
        self,
        current_user: User,
        participant_user_id_str: str,
    ) -> ChatResponse:
        try:
            target_user_id = uuid.UUID(participant_user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid participant user ID format.",
            )

        if target_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot create a conversation with yourself.",
            )

        target_user = self.user_repo.get_by_id(target_user_id)
        if not target_user or not target_user.is_verified or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target registered user does not exist or is not verified.",
            )

        # Check if conversation already exists (idempotent lookup via direct_key)
        conv = self.chat_repo.get_direct_conversation(current_user.id, target_user.id)
        if not conv:
            conv = self.chat_repo.create_direct_conversation(current_user.id, target_user.id)

        other_participant_summary = self._resolve_participant_summary(current_user, target_user)

        last_msg = None
        if conv.messages:
            sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)
            latest = sorted_messages[-1]
            sender_name = (
                current_user.full_name
                if latest.sender_id == current_user.id
                else other_participant_summary.display_name
            )
            last_msg = self._build_message_summary(latest, current_user.id, sender_name=sender_name)

        unread_count = self.chat_repo.count_unread_messages_for_user(conv.id, current_user.id)

        return ChatResponse(
            id=str(conv.id),
            direct_key=conv.direct_key,
            other_participant=other_participant_summary,
            last_message=last_msg,
            unread_count=unread_count,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )

    def list_chats(self, current_user: User) -> List[ChatResponse]:
        conversations = self.chat_repo.list_conversations_for_user(current_user.id)
        results: List[ChatResponse] = []

        for conv in conversations:
            # Find the other participant
            other_part_record = next(
                (p for p in conv.participants if p.user_id != current_user.id),
                None,
            )
            if not other_part_record or not other_part_record.user:
                continue

            target_user = other_part_record.user
            other_participant_summary = self._resolve_participant_summary(current_user, target_user)

            last_msg = None
            if conv.messages:
                sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)
                latest = sorted_messages[-1]
                sender_name = (
                    current_user.full_name
                    if latest.sender_id == current_user.id
                    else other_participant_summary.display_name
                )
                last_msg = self._build_message_summary(latest, current_user.id, sender_name=sender_name)

            unread_count = self.chat_repo.count_unread_messages_for_user(conv.id, current_user.id)

            results.append(
                ChatResponse(
                    id=str(conv.id),
                    direct_key=conv.direct_key,
                    other_participant=other_participant_summary,
                    last_message=last_msg,
                    unread_count=unread_count,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                )
            )

        return results

    def get_messages(
        self,
        current_user: User,
        conversation_id_str: str,
        limit: int = 100,
        offset: int = 0,
    ) -> MessagesListResponse:
        try:
            conv_id = uuid.UUID(conversation_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID format.",
            )

        # Verify authorization: user MUST be a participant
        if not self.chat_repo.is_user_participant(conv_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view messages in this conversation.",
            )

        messages = self.chat_repo.list_messages_for_conversation(conv_id, limit=limit, offset=offset)
        total = self.chat_repo.count_messages(conv_id)

        user_id_str = str(current_user.id)
        items: List[MessageSummary] = []
        for m in messages:
            deleted_by = m.deleted_by_users or []
            if user_id_str in deleted_by:
                continue  # Hidden for this user ("Delete for me")

            items.append(self._build_message_summary(m, current_user.id))

        return MessagesListResponse(
            conversation_id=str(conv_id),
            messages=items,
            total=total,
        )

    def save_message(
        self,
        current_user: User,
        conversation_id_str: str,
        content: str,
        message_type: str = "text",
        media_url: Optional[str] = None,
        media_duration: Optional[int] = None,
    ) -> MessageSummary:
        try:
            conv_id = uuid.UUID(conversation_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID format.",
            )

        if not self.chat_repo.is_user_participant(conv_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to send messages in this conversation.",
            )

        cleaned_content = (content or "").strip()
        if not cleaned_content and not media_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content or media is required.",
            )

        message = self.chat_repo.save_message(
            conversation_id=conv_id,
            sender_id=current_user.id,
            content=cleaned_content if cleaned_content else ("🎙️ Voice note" if message_type == "audio" else ""),
            message_type=message_type,
            media_url=media_url,
            media_duration=media_duration,
        )

        return self._build_message_summary(message, current_user.id, sender_name=current_user.full_name)

    def edit_message(
        self,
        current_user: User,
        conversation_id_str: str,
        message_id_str: str,
        new_content: str,
    ) -> MessageSummary:
        try:
            conv_id = uuid.UUID(conversation_id_str)
            msg_id = uuid.UUID(message_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format.")

        msg = self.chat_repo.get_message_by_id(msg_id)
        if not msg or msg.conversation_id != conv_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

        if msg.sender_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own messages.")

        if msg.is_deleted_everyone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a deleted message.")

        updated = self.chat_repo.edit_message(msg_id, new_content)
        return self._build_message_summary(updated, current_user.id, sender_name=current_user.full_name)

    def delete_message(
        self,
        current_user: User,
        conversation_id_str: str,
        message_id_str: str,
        delete_type: str,
    ) -> MessageSummary:
        try:
            conv_id = uuid.UUID(conversation_id_str)
            msg_id = uuid.UUID(message_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format.")

        msg = self.chat_repo.get_message_by_id(msg_id)
        if not msg or msg.conversation_id != conv_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

        if delete_type == "everyone":
            if msg.sender_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages for everyone.")
            updated = self.chat_repo.delete_message_everyone(msg_id)
        else:
            updated = self.chat_repo.delete_message_for_me(msg_id, current_user.id)

        sender_name = msg.sender.full_name if msg.sender else "User"
        return self._build_message_summary(updated, current_user.id, sender_name=sender_name)

    def toggle_reaction(
        self,
        current_user: User,
        conversation_id_str: str,
        message_id_str: str,
        emoji: str,
    ) -> MessageSummary:
        try:
            conv_id = uuid.UUID(conversation_id_str)
            msg_id = uuid.UUID(message_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format.")

        if not self.chat_repo.is_user_participant(conv_id, current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

        updated = self.chat_repo.add_or_toggle_reaction(
            message_id=msg_id,
            user_id=current_user.id,
            user_name=current_user.full_name,
            emoji=emoji,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

        sender_name = updated.sender.full_name if updated.sender else "User"
        return self._build_message_summary(updated, current_user.id, sender_name=sender_name)

    def mark_messages_read(
        self,
        current_user: User,
        conversation_id_str: str,
    ) -> int:
        try:
            conv_id = uuid.UUID(conversation_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID format.",
            )

        if not self.chat_repo.is_user_participant(conv_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized for this conversation.",
            )

        return self.chat_repo.mark_messages_as_read(conv_id, current_user.id)

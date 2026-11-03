import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.conversation import Conversation
from app.models.conversation_participant import ConversationParticipant
from app.models.message import Message
from app.models.user import User


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_conversation_by_id(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants).joinedload(ConversationParticipant.user),
                selectinload(Conversation.messages),
            )
            .where(Conversation.id == conversation_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_direct_conversation(
        self,
        user1_id: uuid.UUID,
        user2_id: uuid.UUID,
    ) -> Optional[Conversation]:
        direct_key = Conversation.compute_direct_key(user1_id, user2_id)
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants).joinedload(ConversationParticipant.user),
                selectinload(Conversation.messages),
            )
            .where(Conversation.direct_key == direct_key)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_direct_conversation(
        self,
        user1_id: uuid.UUID,
        user2_id: uuid.UUID,
    ) -> Conversation:
        direct_key = Conversation.compute_direct_key(user1_id, user2_id)
        conversation = Conversation(direct_key=direct_key)
        self.db.add(conversation)
        self.db.flush()

        p1 = ConversationParticipant(conversation_id=conversation.id, user_id=user1_id)
        p2 = ConversationParticipant(conversation_id=conversation.id, user_id=user2_id)
        self.db.add_all([p1, p2])

        self.db.commit()
        return self.get_conversation_by_id(conversation.id)

    def list_conversations_for_user(self, user_id: uuid.UUID) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
            .options(
                selectinload(Conversation.participants).joinedload(ConversationParticipant.user),
                selectinload(Conversation.messages).joinedload(Message.sender),
            )
            .where(ConversationParticipant.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def is_user_participant(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(func.count(ConversationParticipant.id)).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
        count = self.db.execute(stmt).scalar_one()
        return count > 0

    def list_messages_for_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Message]:
        stmt = (
            select(Message)
            .options(joinedload(Message.sender))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_messages(self, conversation_id: uuid.UUID) -> int:
        stmt = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        return self.db.execute(stmt).scalar_one()

    def save_message(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
    ) -> Message:
        now = datetime.now(timezone.utc)
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content.strip(),
            created_at=now,
        )
        self.db.add(message)

        # Update conversation's updated_at timestamp
        conv = self.db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = now

        self.db.commit()
        self.db.refresh(message)
        return message

    def mark_messages_as_read(
        self,
        conversation_id: uuid.UUID,
        reader_user_id: uuid.UUID,
    ) -> int:
        """Marks all unread messages from other users in the conversation as read."""
        from sqlalchemy import update
        stmt = (
            update(Message)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_id != reader_user_id,
                    Message.is_read.is_(False),
                )
            )
            .values(is_read=True)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def count_unread_messages_for_user(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Counts unread messages sent by others in this conversation."""
        stmt = select(func.count(Message.id)).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.is_read.is_(False),
            )
        )
        return self.db.execute(stmt).scalar_one()


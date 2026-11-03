import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation_participant import ConversationParticipant
    from app.models.message import Message


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    # Strategy to prevent duplicate 1-to-1 conversations:
    # A canonical key formed by sorting the two participant UUIDs: "uuid_min:uuid_max"
    # The unique constraint strictly prevents race conditions and duplicate private chats.
    direct_key: Mapped[Optional[str]] = mapped_column(
        String(73),
        unique=True,
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    participants: Mapped[List["ConversationParticipant"]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @staticmethod
    def compute_direct_key(user1_id: uuid.UUID, user2_id: uuid.UUID) -> str:
        """Returns deterministic sorted key for two participants in a 1-to-1 conversation."""
        first, second = sorted([str(user1_id), str(user2_id)])
        return f"{first}:{second}"

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, direct_key='{self.direct_key}')>"


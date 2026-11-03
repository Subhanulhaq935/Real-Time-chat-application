import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Boolean, DateTime, ForeignKey, Text, Uuid, String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(
        String(20),
        default="text",
        nullable=False,
    )
    media_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    media_duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    reactions: Mapped[Optional[list]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    is_deleted_everyone: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deleted_by_users: Mapped[Optional[list]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    is_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_messages",
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conv={self.conversation_id}, sender={self.sender_id})>"


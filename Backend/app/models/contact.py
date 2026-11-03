import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    # The user who created the contact / gave the custom name
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The user being named
    contact_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Custom display name visible only to owner_user_id
    custom_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
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

    __table_args__ = (
        # Ensure a user cannot have duplicate contact entries for the same target user
        UniqueConstraint("owner_user_id", "contact_user_id", name="uq_owner_contact"),
        # Prevent a user from adding themselves as a contact
        CheckConstraint("owner_user_id != contact_user_id", name="chk_no_self_contact"),
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[owner_user_id],
        back_populates="owned_contacts",
    )
    contact_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[contact_user_id],
        back_populates="contact_of",
    )

    def __repr__(self) -> str:
        return f"<Contact(owner={self.owner_user_id}, target={self.contact_user_id}, name='{self.custom_name}')>"


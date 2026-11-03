import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class CreateChatRequest(BaseModel):
    participant_user_id: str = Field(..., description="UUID of user to chat with")

    @field_validator("participant_user_id")
    def validate_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v.strip())
            return v.strip()
        except ValueError:
            raise ValueError("Invalid user ID format (must be valid UUID)")


class ParticipantSummary(BaseModel):
    id: str
    email: str
    original_name: str
    display_name: str
    is_online: bool = False
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MessageSummary(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: Optional[str] = None
    content: str
    message_type: str = "text"
    media_url: Optional[str] = None
    media_duration: Optional[int] = None
    reactions: Optional[list] = None
    is_deleted_everyone: bool = False
    deleted_by_users: Optional[list] = None
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    created_at: datetime
    is_mine: bool = False
    is_read: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    id: str
    direct_key: Optional[str] = None
    other_participant: ParticipantSummary
    last_message: Optional[MessageSummary] = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessagesListResponse(BaseModel):
    conversation_id: str
    messages: List[MessageSummary]
    total: int


class SendMessageRequest(BaseModel):
    content: Optional[str] = ""
    message_type: str = "text"
    media_url: Optional[str] = None
    media_duration: Optional[int] = None


class EditMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class DeleteMessageRequest(BaseModel):
    delete_type: str = Field(..., pattern="^(everyone|me)$")


class ReactionRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)



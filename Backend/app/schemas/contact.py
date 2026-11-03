import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


class UserProfileResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    custom_name: Optional[str] = None
    display_name: str
    is_contact: bool = False

    model_config = ConfigDict(from_attributes=True)


class ContactResponse(BaseModel):
    id: str
    contact_user_id: str
    email: str
    original_name: str
    custom_name: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateContactRequest(BaseModel):
    contact_user_id: str = Field(..., description="UUID of target registered user")
    custom_name: str = Field(..., min_length=1, max_length=100, description="Private alias name")

    @field_validator("custom_name")
    def clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Custom name cannot be empty or only whitespace")
        return cleaned


class UpdateContactRequest(BaseModel):
    custom_name: str = Field(..., min_length=1, max_length=100, description="Updated private alias name")

    @field_validator("custom_name")
    def clean_name(cls, v: str) -> str:
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("Custom name cannot be empty or only whitespace")
        return cleaned


class ResetContactResponse(BaseModel):
    message: str
    contact_user_id: str


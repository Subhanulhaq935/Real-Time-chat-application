import uuid
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import (
    UserProfileResponse,
    ContactResponse,
    ResetContactResponse,
)


class ContactService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.contact_repo = ContactRepository(db)

    def search_user_by_email(self, current_user: User, email: str) -> UserProfileResponse:
        normalized_email = email.lower().strip()

        if not normalized_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required for user search.",
            )

        if normalized_email == current_user.email.lower().strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot search for or add your own account as a contact.",
            )

        target_user = self.user_repo.get_by_email(normalized_email)
        if not target_user or not target_user.is_verified or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verified registered user found with this email address.",
            )

        # Check if the current user has given this contact a custom private name
        contact_record = self.contact_repo.get_contact(current_user.id, target_user.id)
        custom_name = contact_record.custom_name if contact_record else None
        display_name = custom_name if custom_name else target_user.full_name

        return UserProfileResponse(
            id=str(target_user.id),
            email=target_user.email,
            full_name=target_user.full_name,
            custom_name=custom_name,
            display_name=display_name,
            is_contact=contact_record is not None,
        )

    def list_contacts(self, current_user: User) -> List[ContactResponse]:
        contacts = self.contact_repo.list_contacts_by_owner(current_user.id)
        results: List[ContactResponse] = []

        for c in contacts:
            target = c.contact_user
            if not target:
                continue
            results.append(
                ContactResponse(
                    id=str(c.id),
                    contact_user_id=str(c.contact_user_id),
                    email=target.email,
                    original_name=target.full_name,
                    custom_name=c.custom_name,
                    display_name=c.custom_name or target.full_name,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )

        return results

    def set_custom_name(
        self,
        current_user: User,
        contact_user_id_str: str,
        custom_name: str,
    ) -> ContactResponse:
        try:
            contact_user_id = uuid.UUID(contact_user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid contact user ID format.",
            )

        if contact_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot add or rename yourself as a contact.",
            )

        target_user = self.user_repo.get_by_id(contact_user_id)
        if not target_user or not target_user.is_verified or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target registered user does not exist or is not verified.",
            )

        contact = self.contact_repo.create_or_update_contact(
            owner_user_id=current_user.id,
            contact_user_id=contact_user_id,
            custom_name=custom_name,
        )

        return ContactResponse(
            id=str(contact.id),
            contact_user_id=str(contact.contact_user_id),
            email=target_user.email,
            original_name=target_user.full_name,
            custom_name=contact.custom_name,
            display_name=contact.custom_name or target_user.full_name,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )

    def reset_custom_name(
        self,
        current_user: User,
        contact_user_id_str: str,
    ) -> ResetContactResponse:
        try:
            contact_user_id = uuid.UUID(contact_user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid contact user ID format.",
            )

        deleted = self.contact_repo.delete_contact(current_user.id, contact_user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No custom contact entry found for this user.",
            )

        return ResetContactResponse(
            message="Custom contact name reset successfully.",
            contact_user_id=str(contact_user_id),
        )


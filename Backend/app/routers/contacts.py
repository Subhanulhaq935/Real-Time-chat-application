from typing import List
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.contact_service import ContactService
from app.schemas.contact import (
    ContactResponse,
    CreateContactRequest,
    UpdateContactRequest,
    ResetContactResponse,
)

router = APIRouter(prefix="/contacts", tags=["Contacts"])


def get_contact_service(db: Session = Depends(get_db)) -> ContactService:
    return ContactService(db)


@router.get(
    "",
    response_model=List[ContactResponse],
    status_code=status.HTTP_200_OK,
    summary="List all contacts saved by the current user",
)
def list_contacts(
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    return service.list_contacts(current_user)


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a registered user as a contact with a private custom name",
)
def create_contact(
    data: CreateContactRequest,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    return service.set_custom_name(
        current_user=current_user,
        contact_user_id_str=data.contact_user_id,
        custom_name=data.custom_name,
    )


@router.patch(
    "/{contact_user_id}",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Set or update private custom contact name",
)
def update_contact_name(
    contact_user_id: str = Path(..., description="UUID of target user"),
    data: UpdateContactRequest = ...,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    return service.set_custom_name(
        current_user=current_user,
        contact_user_id_str=contact_user_id,
        custom_name=data.custom_name,
    )


@router.delete(
    "/{contact_user_id}",
    response_model=ResetContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset custom contact name",
)
def reset_contact_name(
    contact_user_id: str = Path(..., description="UUID of target user"),
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    return service.reset_custom_name(
        current_user=current_user,
        contact_user_id_str=contact_user_id,
    )


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.contact_service import ContactService
from app.schemas.contact import UserProfileResponse

router = APIRouter(prefix="/users", tags=["Users"])


def get_contact_service(db: Session = Depends(get_db)) -> ContactService:
    return ContactService(db)


@router.get(
    "/search",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for a registered verified user by normalized exact email",
)
def search_user_by_email(
    email: str = Query(..., description="Exact email address of registered user"),
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(get_contact_service),
):
    return service.search_user_by_email(current_user=current_user, email=email)


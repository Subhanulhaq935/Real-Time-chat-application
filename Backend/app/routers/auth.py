from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_token_payload
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService
from app.schemas.auth import (
    SignupRequest,
    SignupResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    ResendOTPRequest,
    ResendOTPResponse,
    LoginRequest,
    TokenResponse,
    UserResponse,
    LogoutResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account and receive email OTP",
)
def signup(
    data: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.signup(data)


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify 6-digit OTP code to activate account",
)
def verify_otp(
    data: VerifyOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.verify_otp(data)


@router.post(
    "/resend-otp",
    response_model=ResendOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend a fresh OTP verification code with cooldown limit",
)
def resend_otp(
    data: ResendOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.resend_otp(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and set secure HttpOnly cookie session",
)
def login(
    data: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    token_resp, token_str, max_age = auth_service.login(data)

    # Attach secure HttpOnly cookie for PWA / browser security
    response.set_cookie(
        key="access_token",
        value=token_str,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV != "development",
    )

    return token_resp


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_verified=current_user.is_verified,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke JWT token on server and clear authentication cookie",
)
def logout(
    response: Response,
    payload: dict = Depends(get_token_payload),
    auth_service: AuthService = Depends(get_auth_service),
):
    logout_resp = auth_service.logout(payload)

    # Invalidate client-side HttpOnly cookie
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV != "development",
    )

    return logout_resp



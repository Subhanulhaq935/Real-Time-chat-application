from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    generate_otp_code,
    hash_otp,
    verify_otp_hash,
    create_access_token,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.otp_repository import OTPRepository
from app.repositories.token_repository import TokenRepository
from app.services.email_service import email_service, EmailDeliveryError
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


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.otp_repo = OTPRepository(db)
        self.token_repo = TokenRepository(db)

    def signup(self, data: SignupRequest) -> SignupResponse:
        email = data.email.lower().strip()
        existing_user = self.user_repo.get_by_email(email)

        # Reject if an account is already verified
        if existing_user and existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please log in.",
            )

        hashed_pw = hash_password(data.password)

        if existing_user:
            # Update credentials for unverified account re-attempting signup
            user = self.user_repo.update_unverified_user(
                user=existing_user,
                full_name=data.full_name,
                hashed_password=hashed_pw,
            )
        else:
            # Create user in unverified state
            user = self.user_repo.create(
                email=email,
                hashed_password=hashed_pw,
                full_name=data.full_name,
                is_verified=False,
            )

        # Invalidate previous signup OTPs for this email
        self.otp_repo.invalidate_previous_otps(email=email, purpose="signup")

        # Generate and store a secure 6-digit OTP
        plain_otp = generate_otp_code(length=6)
        hashed_code = hash_otp(plain_otp, email)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

        self.otp_repo.create_otp(
            email=email,
            user_id=user.id,
            hashed_otp=hashed_code,
            purpose="signup",
            expires_at=expires_at,
        )

        # Send OTP via email
        try:
            email_service.send_otp_email(
                recipient_email=email,
                otp_code=plain_otp,
                recipient_name=user.full_name,
            )
        except EmailDeliveryError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Account created, but failed to deliver verification email: {str(e)}",
            )

        return SignupResponse(
            message=f"Verification code sent to {email}. Please verify within {settings.OTP_EXPIRE_MINUTES} minutes.",
            email=email,
        )

    def verify_otp(self, data: VerifyOTPRequest) -> VerifyOTPResponse:
        email = data.email.lower().strip()
        plain_otp = data.otp.strip()

        otp_record = self.otp_repo.get_latest_active_otp(email=email, purpose="signup")
        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active verification code found for this email. Please request a new one.",
            )

        # Check expiration
        now = datetime.now(timezone.utc)
        if otp_record.expires_at < now:
            self.otp_repo.mark_as_used(otp_record)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new one.",
            )

        # Check attempt limits
        if otp_record.attempts >= settings.OTP_MAX_ATTEMPTS:
            self.otp_repo.mark_as_used(otp_record)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. This code is now invalid. Please request a new code.",
            )

        # Verify constant-time HMAC hash
        is_valid = verify_otp_hash(
            plain_otp=plain_otp,
            email=email,
            stored_hash=otp_record.hashed_otp,
        )

        if not is_valid:
            updated_record = self.otp_repo.increment_attempts(otp_record)
            remaining = settings.OTP_MAX_ATTEMPTS - updated_record.attempts
            if remaining <= 0:
                self.otp_repo.mark_as_used(otp_record)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect verification code. Maximum attempts reached. Code is now invalid.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incorrect verification code. {remaining} attempt(s) remaining.",
            )

        # Mark OTP as successfully used
        self.otp_repo.mark_as_used(otp_record)

        # Mark user as verified
        user = self.user_repo.get_by_email(email)
        if user:
            self.user_repo.mark_verified(user)

        return VerifyOTPResponse(
            message="Email verified successfully! You can now log in to your account.",
            email=email,
            is_verified=True,
        )

    def resend_otp(self, data: ResendOTPRequest) -> ResendOTPResponse:
        email = data.email.lower().strip()
        user = self.user_repo.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered account found with this email.",
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account is already verified. You can log in directly.",
            )

        # Check resend cooldown
        latest_otp = self.otp_repo.get_latest_otp(email=email, purpose="signup")
        now = datetime.now(timezone.utc)
        if latest_otp:
            time_since_creation = (now - latest_otp.created_at).total_seconds()
            if time_since_creation < settings.OTP_RESEND_COOLDOWN_SECONDS:
                wait_seconds = int(settings.OTP_RESEND_COOLDOWN_SECONDS - time_since_creation)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {wait_seconds} seconds before requesting a new code.",
                )

        # Invalidate old OTPs
        self.otp_repo.invalidate_previous_otps(email=email, purpose="signup")

        # Generate and store new OTP
        plain_otp = generate_otp_code(length=6)
        hashed_code = hash_otp(plain_otp, email)
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

        self.otp_repo.create_otp(
            email=email,
            user_id=user.id,
            hashed_otp=hashed_code,
            purpose="signup",
            expires_at=expires_at,
        )

        try:
            email_service.send_otp_email(
                recipient_email=email,
                otp_code=plain_otp,
                recipient_name=user.full_name,
            )
        except EmailDeliveryError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to deliver verification email: {str(e)}",
            )

        return ResendOTPResponse(
            message="A new verification code has been sent to your email.",
            email=email,
            cooldown_seconds=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )

    def login(self, data: LoginRequest) -> tuple[TokenResponse, str, int]:
        email = data.email.lower().strip()
        user = self.user_repo.get_by_email(email)

        # Constant-time comparison check & generic error on missing user or bad password
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support.",
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not verified. Please verify your email before logging in.",
            )

        # Generate JWT with unique jti claim
        token_str, jti, expires_at = create_access_token(
            user_id=str(user.id),
            email=user.email,
        )

        max_age_seconds = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

        response_data = TokenResponse(
            access_token=token_str,
            token_type="bearer",
            expires_in=max_age_seconds,
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                is_verified=user.is_verified,
            ),
        )

        return response_data, token_str, max_age_seconds

    def logout(self, payload: dict) -> LogoutResponse:
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            self.token_repo.revoke_token(jti=jti, expires_at=expires_at)

        return LogoutResponse(message="Successfully logged out.")



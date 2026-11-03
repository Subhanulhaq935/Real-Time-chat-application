import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.email_otp import EmailOTP


class OTPRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_otp(
        self,
        email: str,
        hashed_otp: str,
        expires_at: datetime,
        purpose: str = "signup",
        user_id: Optional[uuid.UUID] = None,
    ) -> EmailOTP:
        otp_record = EmailOTP(
            email=email.lower().strip(),
            user_id=user_id,
            hashed_otp=hashed_otp,
            purpose=purpose,
            attempts=0,
            is_used=False,
            expires_at=expires_at,
        )
        self.db.add(otp_record)
        self.db.commit()
        self.db.refresh(otp_record)
        return otp_record

    def get_latest_active_otp(
        self,
        email: str,
        purpose: str = "signup",
    ) -> Optional[EmailOTP]:
        stmt = (
            select(EmailOTP)
            .where(
                EmailOTP.email == email.lower().strip(),
                EmailOTP.purpose == purpose,
                EmailOTP.is_used == False,  # noqa: E712
            )
            .order_by(EmailOTP.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def get_latest_otp(
        self,
        email: str,
        purpose: str = "signup",
    ) -> Optional[EmailOTP]:
        stmt = (
            select(EmailOTP)
            .where(
                EmailOTP.email == email.lower().strip(),
                EmailOTP.purpose == purpose,
            )
            .order_by(EmailOTP.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def increment_attempts(self, otp_record: EmailOTP) -> EmailOTP:
        otp_record.attempts += 1
        self.db.commit()
        self.db.refresh(otp_record)
        return otp_record

    def mark_as_used(self, otp_record: EmailOTP) -> EmailOTP:
        otp_record.is_used = True
        self.db.commit()
        self.db.refresh(otp_record)
        return otp_record

    def invalidate_previous_otps(
        self,
        email: str,
        purpose: str = "signup",
    ) -> None:
        stmt = (
            update(EmailOTP)
            .where(
                EmailOTP.email == email.lower().strip(),
                EmailOTP.purpose == purpose,
                EmailOTP.is_used == False,  # noqa: E712
            )
            .values(is_used=True)
        )
        self.db.execute(stmt)
        self.db.commit()


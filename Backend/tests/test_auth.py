import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.email_otp import EmailOTP
from app.core.security import hash_otp

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_signup_validation_errors():
    # Weak password
    res = client.post("/auth/signup", json={
        "full_name": "Test User",
        "email": "invalid_email_format",
        "password": "short",
    })
    assert res.status_code == 422


def test_signup_and_verify_success(db):
    unique_email = f"signup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "John Doe",
        "email": unique_email,
        "password": "Password123!",
    }

    # Mock send_otp_email so network SMTP is not needed in test suite
    with patch("app.services.email_service.email_service.send_otp_email") as mock_email:
        res = client.post("/auth/signup", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == unique_email
        assert mock_email.called

    # Query the generated OTP record
    otp_record = db.execute(
        select(EmailOTP).where(EmailOTP.email == unique_email, EmailOTP.is_used == False)
    ).scalar_one_or_none()
    assert otp_record is not None
    assert otp_record.attempts == 0

    # User should be unverified initially
    user = db.execute(
        select(User).where(User.email == unique_email)
    ).scalar_one_or_none()
    assert user is not None
    assert user.is_verified is False

    # Mock OTP code to verify
    # We can compute the matching code since we know how hash_otp works
    test_code = "654321"
    otp_record.hashed_otp = hash_otp(test_code, unique_email)
    db.commit()

    # Attempt verification
    verify_res = client.post("/auth/verify-otp", json={
        "email": unique_email,
        "otp": test_code,
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True

    # User must now be verified
    db.refresh(user)
    assert user.is_verified is True

    # Try duplicate signup for verified user
    dup_res = client.post("/auth/signup", json=payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # Cleanup
    db.delete(user)
    db.commit()


def test_verify_invalid_otp_and_attempt_limit(db):
    unique_email = f"attempts_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Jane Doe",
        "email": unique_email,
        "password": "Password123!",
    }

    with patch("app.services.email_service.email_service.send_otp_email"):
        res = client.post("/auth/signup", json=payload)
        assert res.status_code == 201

    # Attempt invalid code
    bad_res = client.post("/auth/verify-otp", json={
        "email": unique_email,
        "otp": "000000",
    })
    assert bad_res.status_code == 400
    assert "remaining" in bad_res.json()["detail"].lower()

    # Simulate max attempts reached
    otp_record = db.execute(
        select(EmailOTP).where(EmailOTP.email == unique_email, EmailOTP.is_used == False)
    ).scalar_one_or_none()
    assert otp_record is not None
    otp_record.attempts = 5
    db.commit()

    # Try again with max attempts exceeded
    locked_res = client.post("/auth/verify-otp", json={
        "email": unique_email,
        "otp": "000000",
    })
    assert locked_res.status_code == 400
    assert "maximum" in locked_res.json()["detail"].lower() or "too many" in locked_res.json()["detail"].lower()

    # Cleanup
    user = db.execute(select(User).where(User.email == unique_email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()


def test_verify_expired_otp(db):
    unique_email = f"expired_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Bob Smith",
        "email": unique_email,
        "password": "Password123!",
    }

    with patch("app.services.email_service.email_service.send_otp_email"):
        res = client.post("/auth/signup", json=payload)
        assert res.status_code == 201

    # Artificially set expiry in the past
    otp_record = db.execute(
        select(EmailOTP).where(EmailOTP.email == unique_email, EmailOTP.is_used == False)
    ).scalar_one_or_none()
    otp_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    expired_res = client.post("/auth/verify-otp", json={
        "email": unique_email,
        "otp": "123456",
    })
    assert expired_res.status_code == 400
    assert "expired" in expired_res.json()["detail"].lower()

    # Cleanup
    user = db.execute(select(User).where(User.email == unique_email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()


def test_resend_otp_cooldown(db):
    unique_email = f"cooldown_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Alice Cooldown",
        "email": unique_email,
        "password": "Password123!",
    }

    with patch("app.services.email_service.email_service.send_otp_email"):
        client.post("/auth/signup", json=payload)

        # Immediate resend should trigger 429 Too Many Requests
        too_soon_res = client.post("/auth/resend-otp", json={"email": unique_email})
        assert too_soon_res.status_code == 429
        assert "seconds" in too_soon_res.json()["detail"]

    # Cleanup
    user = db.execute(select(User).where(User.email == unique_email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()


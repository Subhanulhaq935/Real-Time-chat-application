import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_login_and_logout_flow(db):
    unique_email = f"auth_flow_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "SecurePassword123"

    # Create a verified user directly in DB
    user = User(
        email=unique_email,
        hashed_password=hash_password(raw_password),
        full_name="Verified Flow User",
        is_verified=True,
    )
    db.add(user)
    db.commit()

    # 1. Test Login Success
    login_res = client.post("/auth/login", json={
        "email": unique_email,
        "password": raw_password,
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == unique_email
    assert "access_token" in login_res.cookies

    token = data["access_token"]

    # 2. Test GET /auth/me with Bearer token
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == unique_email
    assert me_data["full_name"] == "Verified Flow User"
    assert "hashed_password" not in me_data

    # 3. Test GET /auth/me using Cookie
    cookie_me_res = client.get("/auth/me", cookies={"access_token": token})
    assert cookie_me_res.status_code == 200
    assert cookie_me_res.json()["email"] == unique_email

    # 4. Test POST /auth/logout
    logout_res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    assert "logged out" in logout_res.json()["message"].lower()

    # 5. Verify the revoked token cannot be reused
    revoked_check = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked_check.status_code == 401
    assert "revoked" in revoked_check.json()["detail"].lower()

    # Cleanup
    db.delete(user)
    db.commit()


def test_login_invalid_credentials(db):
    unique_email = f"wrong_pw_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        hashed_password=hash_password("RealPassword123"),
        full_name="User Wrong PW",
        is_verified=True,
    )
    db.add(user)
    db.commit()

    # Wrong password
    bad_res = client.post("/auth/login", json={
        "email": unique_email,
        "password": "WrongPassword999",
    })
    assert bad_res.status_code == 401
    assert "invalid email or password" in bad_res.json()["detail"].lower()

    # Non-existent user
    non_existent_res = client.post("/auth/login", json={
        "email": f"nobody_{uuid.uuid4().hex[:8]}@example.com",
        "password": "SomePassword123",
    })
    assert non_existent_res.status_code == 401
    assert "invalid email or password" in non_existent_res.json()["detail"].lower()

    # Cleanup
    db.delete(user)
    db.commit()


def test_login_unverified_account(db):
    unique_email = f"unverified_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        hashed_password=hash_password("Password123"),
        full_name="Unverified User",
        is_verified=False,
    )
    db.add(user)
    db.commit()

    # Attempt login on unverified user
    res = client.post("/auth/login", json={
        "email": unique_email,
        "password": "Password123",
    })
    assert res.status_code == 403
    assert "not verified" in res.json()["detail"].lower()

    # Cleanup
    db.delete(user)
    db.commit()


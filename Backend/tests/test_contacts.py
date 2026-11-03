import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password, create_access_token

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_user_search_and_contacts_lifecycle(db):
    email_ali = f"ali_{uuid.uuid4().hex[:8]}@example.com"
    email_ahmed = f"ahmed_{uuid.uuid4().hex[:8]}@example.com"
    email_unverified = f"unverified_{uuid.uuid4().hex[:8]}@example.com"

    ali = User(
        email=email_ali,
        hashed_password=hash_password("Password123"),
        full_name="Ali Khan",
        is_verified=True,
    )
    ahmed = User(
        email=email_ahmed,
        hashed_password=hash_password("Password123"),
        full_name="Ahmed Raza",
        is_verified=True,
    )
    unverified_user = User(
        email=email_unverified,
        hashed_password=hash_password("Password123"),
        full_name="Pending User",
        is_verified=False,
    )
    db.add_all([ali, ahmed, unverified_user])
    db.commit()

    token_ali, _, _ = create_access_token(user_id=str(ali.id), email=ali.email)
    headers_ali = {"Authorization": f"Bearer {token_ali}"}

    # 1. Search for Ahmed
    search_res = client.get(f"/users/search?email={email_ahmed}", headers=headers_ali)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["email"] == email_ahmed
    assert search_data["full_name"] == "Ahmed Raza"
    assert search_data["display_name"] == "Ahmed Raza"
    assert search_data["is_contact"] is False
    assert "hashed_password" not in search_data

    # 2. Search for unverified user should return 404
    unverified_res = client.get(f"/users/search?email={email_unverified}", headers=headers_ali)
    assert unverified_res.status_code == 404

    # 3. Search for self should return 400
    self_search_res = client.get(f"/users/search?email={email_ali}", headers=headers_ali)
    assert self_search_res.status_code == 400
    assert "own account" in self_search_res.json()["detail"].lower()

    # 4. Ali sets custom name for Ahmed: "Best Friend"
    set_name_res = client.patch(
        f"/contacts/{ahmed.id}",
        json={"custom_name": "Best Friend"},
        headers=headers_ali,
    )
    assert set_name_res.status_code == 200
    contact_data = set_name_res.json()
    assert contact_data["custom_name"] == "Best Friend"
    assert contact_data["original_name"] == "Ahmed Raza"
    assert contact_data["display_name"] == "Best Friend"

    # 5. Verify Ali's search now shows "Best Friend" as display_name
    search_after_res = client.get(f"/users/search?email={email_ahmed}", headers=headers_ali)
    assert search_after_res.status_code == 200
    assert search_after_res.json()["display_name"] == "Best Friend"
    assert search_after_res.json()["is_contact"] is True

    # 6. Verify Ahmed's own profile is still "Ahmed Raza"
    token_ahmed, _, _ = create_access_token(user_id=str(ahmed.id), email=ahmed.email)
    headers_ahmed = {"Authorization": f"Bearer {token_ahmed}"}
    ahmed_me_res = client.get("/auth/me", headers=headers_ahmed)
    assert ahmed_me_res.status_code == 200
    assert ahmed_me_res.json()["full_name"] == "Ahmed Raza"

    # 7. List contacts for Ali
    list_res = client.get("/contacts", headers=headers_ali)
    assert list_res.status_code == 200
    contacts_list = list_res.json()
    assert len(contacts_list) == 1
    assert contacts_list[0]["custom_name"] == "Best Friend"
    assert contacts_list[0]["contact_user_id"] == str(ahmed.id)

    # 8. Reset custom name
    reset_res = client.delete(f"/contacts/{ahmed.id}", headers=headers_ali)
    assert reset_res.status_code == 200
    assert "reset" in reset_res.json()["message"].lower()

    # 9. Verify contact list is now empty for Ali
    empty_list_res = client.get("/contacts", headers=headers_ali)
    assert empty_list_res.status_code == 200
    assert len(empty_list_res.json()) == 0

    # Cleanup
    db.delete(ali)
    db.delete(ahmed)
    db.delete(unverified_user)
    db.commit()


def test_cannot_rename_self(db):
    user = User(
        email=f"self_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("pw"),
        full_name="Self User",
        is_verified=True,
    )
    db.add(user)
    db.commit()

    token, _, _ = create_access_token(user_id=str(user.id), email=user.email)
    res = client.patch(
        f"/contacts/{user.id}",
        json={"custom_name": "Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "yourself" in res.json()["detail"].lower()

    db.delete(user)
    db.commit()


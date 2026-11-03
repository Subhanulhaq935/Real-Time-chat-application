import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
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


def test_conversations_and_messaging_lifecycle(db):
    user_a = User(
        email=f"alice_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123"),
        full_name="Alice Wonderland",
        is_verified=True,
    )
    user_b = User(
        email=f"bob_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123"),
        full_name="Bob Builder",
        is_verified=True,
    )
    user_c = User(
        email=f"charlie_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123"),
        full_name="Charlie Outsider",
        is_verified=True,
    )
    db.add_all([user_a, user_b, user_c])
    db.commit()

    token_a, _, _ = create_access_token(user_id=str(user_a.id), email=user_a.email)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b, _, _ = create_access_token(user_id=str(user_b.id), email=user_b.email)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    token_c, _, _ = create_access_token(user_id=str(user_c.id), email=user_c.email)
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # 1. Alice creates conversation with Bob
    create_res = client.post(
        "/chats",
        json={"participant_user_id": str(user_b.id)},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    chat_data = create_res.json()
    conv_id = chat_data["id"]
    assert chat_data["other_participant"]["email"] == user_b.email

    # 2. Duplicate prevention test: calling POST /chats again returns existing conversation
    dup_res = client.post(
        "/chats",
        json={"participant_user_id": str(user_b.id)},
        headers=headers_a,
    )
    assert dup_res.status_code == 201
    assert dup_res.json()["id"] == conv_id

    # 3. Bob calling POST /chats with Alice also gets the SAME conversation
    bob_chat_res = client.post(
        "/chats",
        json={"participant_user_id": str(user_a.id)},
        headers=headers_b,
    )
    assert bob_chat_res.status_code == 201
    assert bob_chat_res.json()["id"] == conv_id

    # 4. Cannot chat with self
    self_res = client.post(
        "/chats",
        json={"participant_user_id": str(user_a.id)},
        headers=headers_a,
    )
    assert self_res.status_code == 400

    # 5. Alice sends a REST message
    send_res = client.post(
        f"/chats/{conv_id}/messages",
        json={"content": "Hi Bob, welcome to the real-time chat!"},
        headers=headers_a,
    )
    assert send_res.status_code == 201
    msg_data = send_res.json()
    assert msg_data["content"] == "Hi Bob, welcome to the real-time chat!"
    assert msg_data["is_mine"] is True

    # 6. Alice retrieves message history
    history_res = client.get(f"/chats/{conv_id}/messages", headers=headers_a)
    assert history_res.status_code == 200
    messages = history_res.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Hi Bob, welcome to the real-time chat!"

    # 7. Charlie (non-participant) attempts to view messages -> 403 Forbidden
    unauthorized_res = client.get(f"/chats/{conv_id}/messages", headers=headers_c)
    assert unauthorized_res.status_code == 403

    # 8. Test WebSocket real-time delivery
    # Bob connects via WebSocket with query token
    with client.websocket_connect(f"/ws/chats/{conv_id}?token={token_b}") as ws_bob:
        init_data = ws_bob.receive_json()
        assert init_data["type"] == "connection_established"

        # Check if messages_read was broadcasted because Bob read Alice's message
        peek = ws_bob.receive_json()
        if peek["type"] == "messages_read":
            assert peek["conversation_id"] == conv_id
        else:
            assert peek["type"] == "connection_established"

        # Bob sends a message via WebSocket
        ws_bob.send_json({"content": "Hey Alice, WebSocket messaging works!"})

        # Bob receives the broadcasted message
        received = ws_bob.receive_json()
        assert received["type"] == "new_message"
        assert received["message"]["content"] == "Hey Alice, WebSocket messaging works!"
        assert received["message"]["sender_name"] == "Bob Builder"
        assert received["message"]["is_read"] is False

    # 9. Verify the message was persisted to PostgreSQL
    db.expire_all()
    final_history = client.get(f"/chats/{conv_id}/messages", headers=headers_a).json()
    assert len(final_history["messages"]) == 2
    assert final_history["messages"][1]["content"] == "Hey Alice, WebSocket messaging works!"

    # 10. Non-participant Charlie WebSocket connection is rejected with 1008
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/chats/{conv_id}?token={token_c}"):
            pass
    assert exc_info.value.code == 1008

    # Cleanup
    db.delete(user_a)
    db.delete(user_b)
    db.delete(user_c)
    db.commit()


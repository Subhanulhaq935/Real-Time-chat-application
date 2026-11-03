import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.models import (
    User,
    EmailOTP,
    Conversation,
    ConversationParticipant,
    Message,
    Contact,
)


@pytest.fixture
def db_session():
    """Provides a transactional database session rolled back or cleaned up after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_create_user(db_session):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        hashed_password="hashed_pw_test",
        full_name="Alice Wonderland",
        is_verified=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == unique_email
    assert user.is_verified is False
    assert user.created_at is not None

    # Cleanup
    db_session.delete(user)
    db_session.commit()


def test_user_email_unique_constraint(db_session):
    unique_email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
    user1 = User(
        email=unique_email,
        hashed_password="pw1",
        full_name="User One",
    )
    user2 = User(
        email=unique_email,
        hashed_password="pw2",
        full_name="User Two",
    )
    db_session.add(user1)
    db_session.commit()

    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    # Cleanup
    db_session.delete(user1)
    db_session.commit()


def test_email_otp(db_session):
    unique_email = f"otp_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        hashed_password="pw",
        full_name="OTP User",
    )
    db_session.add(user)
    db_session.commit()

    otp = EmailOTP(
        email=unique_email,
        user_id=user.id,
        hashed_otp="hashed_123456",
        purpose="signup",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(otp)
    db_session.commit()
    db_session.refresh(otp)

    assert otp.id is not None
    assert otp.attempts == 0
    assert otp.is_used is False
    assert otp.user.id == user.id

    # Cleanup (cascading delete on user deletes email_otps)
    db_session.delete(user)
    db_session.commit()

    # Confirm OTP was cascade-deleted
    found_otp = db_session.get(EmailOTP, otp.id)
    assert found_otp is None


def test_conversation_and_duplicate_prevention(db_session):
    user1 = User(
        email=f"u1_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="User One",
    )
    user2 = User(
        email=f"u2_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="User Two",
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    # Compute direct key for 1-to-1 conversation
    direct_key = Conversation.compute_direct_key(user1.id, user2.id)

    conv1 = Conversation(direct_key=direct_key)
    db_session.add(conv1)
    db_session.commit()

    p1 = ConversationParticipant(conversation_id=conv1.id, user_id=user1.id)
    p2 = ConversationParticipant(conversation_id=conv1.id, user_id=user2.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    # Verify duplicate direct conversation is rejected by unique constraint
    conv2 = Conversation(direct_key=direct_key)
    db_session.add(conv2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Verify duplicate participant in the same conversation is rejected
    duplicate_p1 = ConversationParticipant(conversation_id=conv1.id, user_id=user1.id)
    db_session.add(duplicate_p1)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Cleanup
    db_session.delete(user1)
    db_session.delete(user2)
    db_session.commit()


def test_message_creation_and_cascade(db_session):
    user1 = User(
        email=f"u1_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="Sender",
    )
    user2 = User(
        email=f"u2_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="Receiver",
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    direct_key = Conversation.compute_direct_key(user1.id, user2.id)
    conv = Conversation(direct_key=direct_key)
    db_session.add(conv)
    db_session.commit()

    msg = Message(
        conversation_id=conv.id,
        sender_id=user1.id,
        content="Hello, this is a real-time message test!",
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    assert msg.id is not None
    assert msg.is_read is False
    assert msg.sender.full_name == "Sender"
    assert msg.conversation.id == conv.id

    # Cleanup
    db_session.delete(user1)
    db_session.delete(user2)
    db_session.commit()


def test_contact_renaming_and_constraints(db_session):
    user_ali = User(
        email=f"ali_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="Ali Khan",
    )
    user_ahmed = User(
        email=f"ahmed_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="pw",
        full_name="Ahmed Raza",
    )
    db_session.add_all([user_ali, user_ahmed])
    db_session.commit()

    # Ali gives Ahmed a custom private name "Best Friend"
    contact = Contact(
        owner_user_id=user_ali.id,
        contact_user_id=user_ahmed.id,
        custom_name="Best Friend",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    assert contact.custom_name == "Best Friend"
    assert user_ahmed.full_name == "Ahmed Raza"  # Ahmed's actual account name remains unaffected

    # Ensure Ali cannot create a duplicate contact entry for Ahmed
    dup_contact = Contact(
        owner_user_id=user_ali.id,
        contact_user_id=user_ahmed.id,
        custom_name="Another Label",
    )
    db_session.add(dup_contact)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Ensure a user cannot add themselves as contact (chk_no_self_contact check constraint)
    self_contact = Contact(
        owner_user_id=user_ali.id,
        contact_user_id=user_ali.id,
        custom_name="Me Myself",
    )
    db_session.add(self_contact)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Cleanup
    db_session.delete(user_ali)
    db_session.delete(user_ahmed)
    db_session.commit()


import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
import bcrypt
import jwt
from app.core.config import settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt with automatic salt generation."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def generate_otp_code(length: int = 6) -> str:
    """Generates a cryptographically secure numeric OTP."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def hash_otp(otp: str, email: str) -> str:
    """Hashes an OTP code using HMAC-SHA256 with the app's secret key and email as salt."""
    key = settings.SECRET_KEY.encode("utf-8")
    msg = f"{email.lower().strip()}:{otp.strip()}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_otp_hash(plain_otp: str, email: str, stored_hash: str) -> bool:
    """Verifies a plain OTP against its stored HMAC hash in constant time."""
    computed_hash = hash_otp(plain_otp, email)
    return hmac.compare_digest(computed_hash, stored_hash)


def create_access_token(
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, str, datetime]:
    """
    Creates a signed JWT access token.
    Returns: (token_str, jti, expires_at_datetime)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expires_at = now + expires_delta
    else:
        expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email.lower().strip(),
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, jti, expires_at


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token.
    Raises jwt.PyJWTError on invalid or expired token.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "exp", "jti"]},
    )


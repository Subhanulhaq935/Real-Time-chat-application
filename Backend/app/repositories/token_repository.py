from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.revoked_token import RevokedToken


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def revoke_token(self, jti: str, expires_at: datetime) -> RevokedToken:
        revoked = RevokedToken(jti=jti, expires_at=expires_at)
        self.db.add(revoked)
        self.db.commit()
        self.db.refresh(revoked)
        return revoked

    def is_token_revoked(self, jti: str) -> bool:
        stmt = select(RevokedToken).where(RevokedToken.jti == jti)
        result = self.db.execute(stmt).scalar_one_or_none()
        return result is not None


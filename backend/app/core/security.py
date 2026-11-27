from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID, token_version: int = 0) -> str:
    if isinstance(token_version, bool) or not isinstance(token_version, int) or token_version < 0:
        raise ValueError("Token version must be a non-negative integer")
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires, "ver": token_version},
        settings.signing_key(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> tuple[UUID, int]:
    settings = get_settings()
    payload = jwt.decode(token, settings.signing_key(), algorithms=[ALGORITHM])
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise ValueError("Token subject is missing")
    token_version = payload.get("ver")
    if isinstance(token_version, bool) or not isinstance(token_version, int) or token_version < 0:
        raise ValueError("Token version is missing or invalid")
    return UUID(subject), token_version

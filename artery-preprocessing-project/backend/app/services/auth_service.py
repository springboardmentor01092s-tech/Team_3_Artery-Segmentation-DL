from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import DEFAULT_REGISTRATION_ROLE
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.auth import LoginRequest, RegisterRequest
from app.security.jwt import create_access_token
from app.security.passwords import hash_password, verify_password
from app.utils.audit import record_audit


def register_user(db: Session, payload: RegisterRequest) -> User:
    existing = user_repo.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=DEFAULT_REGISTRATION_ROLE.value,
        is_active=True,
    )
    db.add(user)
    db.flush()
    record_audit(db, "user.register", actor_id=user.id, resource_type="user", resource_id=user.id)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, payload: LoginRequest) -> tuple[User, str]:
    user = user_repo.get_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        record_audit(db, "auth.login_failed", resource_type="user", metadata={"email": payload.email.lower()})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated.")
    token = create_access_token(user.id, user.role)
    record_audit(db, "auth.login", actor_id=user.id, resource_type="user", resource_id=user.id)
    db.commit()
    return user, token


def token_response(token: str) -> dict:
    settings = get_settings()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.access_token_expire_minutes,
    }

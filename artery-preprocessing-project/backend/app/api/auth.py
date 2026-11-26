from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfileUpdate, UserPublic
from app.security.passwords import hash_password
from app.services import auth_service
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserPublic, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    _ = request
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    _ = request
    user, token = auth_service.authenticate(db, payload)
    _ = user
    return auth_service.token_response(token)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(payload: UserProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.full_name:
        user.full_name = payload.full_name.strip()
    if payload.password:
        user.password_hash = hash_password(payload.password)
    record_audit(db, "user.profile_update", actor_id=user.id, resource_type="user", resource_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout")
def logout(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record_audit(db, "auth.logout", actor_id=user.id, resource_type="user", resource_id=user.id)
    db.commit()
    return {"message": "Logged out. Discard the access token on the client."}

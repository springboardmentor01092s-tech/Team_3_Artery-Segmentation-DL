from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from app.api.deps import get_authenticated_user, get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.security_state import EmailChangeVerification
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import (
    EmailChangeVerificationRead,
    EmailChangeVerificationRequest,
    PasswordChange,
    ProfileUpdate,
    ProfileUpdateRead,
    UserRead,
)
from app.services.email_delivery import (
    EmailDeliveryNotConfigured,
    send_email_change_verification,
    validate_email_delivery_config,
)
from app.services.login_rate_limit import record_login_attempt

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    try:
        retry_after = record_login_attempt(
            db,
            client_host=request.client.host if request.client else "unknown",
            email=str(payload.email),
            settings=settings,
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable",
        ) from None
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.id, user.token_version),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_authenticated_user)) -> User:
    return current_user


@router.patch("/me/profile", response_model=ProfileUpdateRead)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileUpdateRead:
    user = db.scalar(
        select(User)
        .where(User.id == current_user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    supplied = payload.model_fields_set
    verification_sent = False
    pending_email: str | None = None
    raw_token: str | None = None
    if "email" in supplied:
        normalized_email = str(payload.email).strip().lower()
        if normalized_email != user.email.lower():
            settings = get_settings()
            try:
                validate_email_delivery_config(settings)
            except EmailDeliveryNotConfigured:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Email changes are unavailable until email delivery is configured",
                ) from None
            duplicate_id = db.scalar(
                select(User.id).where(
                    func.lower(User.email) == normalized_email,
                    User.id != user.id,
                )
            )
            if duplicate_id is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
            previous = db.scalar(
                select(EmailChangeVerification)
                .where(EmailChangeVerification.user_id == user.id)
                .with_for_update()
            )
            now = datetime.now(timezone.utc)
            if previous is not None:
                created_at = previous.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if created_at + timedelta(seconds=60) > now:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Please wait before requesting another email verification",
                    )
                db.delete(previous)
            raw_token = secrets.token_urlsafe(32)
            pending_email = normalized_email
            db.add(EmailChangeVerification(
                user_id=user.id,
                pending_email=pending_email,
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=now + timedelta(minutes=settings.email_verification_ttl_minutes),
            ))
            verification_sent = True
    if "full_name" in supplied:
        user.full_name = payload.full_name
    try:
        if pending_email is not None and raw_token is not None:
            try:
                send_email_change_verification(get_settings(), pending_email, raw_token)
            except Exception:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Email verification could not be sent; the current email address is unchanged",
                ) from None
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return ProfileUpdateRead.model_validate(user).model_copy(update={"email_verification_sent": verification_sent})


@router.post("/verify-email-change", response_model=EmailChangeVerificationRead)
def verify_email_change(
    payload: EmailChangeVerificationRequest,
    db: Session = Depends(get_db),
) -> EmailChangeVerificationRead:
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    verification = db.scalar(
        select(EmailChangeVerification)
        .where(EmailChangeVerification.token_hash == token_hash)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if verification is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification link is invalid or expired")
    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification link is invalid or expired")
    user = db.scalar(
        select(User)
        .where(User.id == verification.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification link is invalid or expired")
    duplicate_id = db.scalar(
        select(User.id).where(func.lower(User.email) == verification.pending_email.lower(), User.id != user.id)
    )
    if duplicate_id is not None:
        db.delete(verification)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested email address is no longer available")
    user.email = verification.pending_email
    user.token_version += 1
    db.delete(verification)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested email address is no longer available") from None
    db.refresh(user)
    return EmailChangeVerificationRead(detail="Email address verified. Sign in again using the new address.")


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> User:
    # Lock and refresh the row after authentication so concurrent admin resets
    # cannot be overwritten by a password change based on an older hash.
    user = db.scalar(
        select(User)
        .where(User.id == current_user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if request.state.auth_token_version != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version += 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserDeletionCleanupRead,
    UserDeletionRead,
    UserDeletionRetryRead,
    UserPasswordReset,
    UserRead,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.services.user_deletion import (
    UserDeletionNotFound,
    UserDeletionRejected,
    UserDeletionTransactionError,
    delete_regular_user,
    list_pending_user_deletion_cleanups,
    retry_user_deletion_cleanup,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.get("/deletion-cleanups", response_model=list[UserDeletionCleanupRead])
def list_deletion_cleanups(_: User = Depends(require_admin)) -> list[dict[str, object]]:
    try:
        return list_pending_user_deletion_cleanups(get_settings().analysis_output_directory)
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail="Deletion cleanup status is unavailable") from None


@router.post("/deletion-cleanups/{cleanup_id}/retry", response_model=UserDeletionRetryRead)
def retry_deletion_cleanup(
    cleanup_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, object]:
    try:
        return retry_user_deletion_cleanup(db, cleanup_id, get_settings())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Deletion cleanup record not found") from None
    except (ValueError, OSError):
        raise HTTPException(status_code=409, detail="Deletion cleanup record could not be safely processed") from None


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> User:
    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=UserDeletionRead)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> dict[str, object]:
    try:
        return delete_regular_user(db, user_id, current_admin.id, get_settings())
    except UserDeletionNotFound:
        raise HTTPException(status_code=404, detail="User not found") from None
    except UserDeletionRejected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UserDeletionTransactionError as exc:
        if exc.args and exc.args[0] is not None:
            raise HTTPException(
                status_code=503,
                detail=f"Deletion outcome could not be confirmed. Cleanup record {exc.args[0]} is available for safe retry.",
            ) from None
        raise HTTPException(status_code=500, detail="User deletion failed; the database transaction was rolled back.") from None
    except (ValueError, OSError):
        raise HTTPException(status_code=503, detail="Managed storage could not be verified; no account data was deleted.") from None


def lock_active_administrators(db: Session) -> list[User]:
    """Serialize admin role/status changes by locking active admin rows in stable order."""
    query = (
        select(User)
        .where(User.role == "admin", User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update()
    )
    return list(db.scalars(query).all())


def get_user_for_update(db: Session, user_id: UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    active_admins = lock_active_administrators(db)
    user = get_user_for_update(db, user_id)
    if user.role == "admin" and user.is_active and payload.role != "admin" and len(active_admins) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot demote the last active administrator")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> User:
    active_admins = lock_active_administrators(db)
    user = get_user_for_update(db, user_id)
    if user_id == current_admin.id and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrators cannot deactivate their own account")
    if user.role == "admin" and user.is_active and not payload.is_active and len(active_admins) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot deactivate the last active administrator")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/password-reset", response_model=UserRead)
def reset_user_password(
    user_id: UUID,
    payload: UserPasswordReset,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> User:
    user = get_user_for_update(db, user_id)
    user.password_hash = hash_password(payload.temporary_password)
    user.must_change_password = True
    user.token_version += 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return user

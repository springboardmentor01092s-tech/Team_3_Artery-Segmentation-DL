from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.permissions import UserRole
from app.models.audit import AuditLog
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.admin import AdminUserOut, AdminUserUpdate, AuditLogOut
from app.utils.audit import record_audit

router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return user_repo.list_users(db)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = user_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")
    requested_role = payload.role.value if isinstance(payload.role, UserRole) else payload.role
    removes_active_admin = (
        user.role == UserRole.ADMINISTRATOR.value
        and user.is_active
        and (payload.is_active is False or requested_role not in (None, UserRole.ADMINISTRATOR.value))
    )
    if removes_active_admin:
        active_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMINISTRATOR.value,
                User.is_active.is_(True),
            )
        )
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active administrator cannot be deactivated or demoted.",
            )
    if payload.role is not None:
        user.role = requested_role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    record_audit(
        db,
        "admin.user_update",
        actor_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"role": user.role, "is_active": user.is_active},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    ACCESS_TYPE_ASSIGNED,
    VALID_ACCESS_TYPES,
    Permission,
    has_permission,
)
from app.models.case import Case
from app.models.case_access import CaseAccess
from app.models.user import User
from app.repositories import cases as case_repo
from app.repositories import users as user_repo
from app.schemas.case import AccessCandidateOut, CaseAccessOut, CaseCreate, CaseOut, CaseUpdate, ImageSummary
from app.utils.audit import record_audit


def _latest_image_summary(case: Case) -> ImageSummary | None:
    if not case.images:
        return None
    image = sorted(case.images, key=lambda item: item.uploaded_at, reverse=True)[0]
    return ImageSummary.model_validate(image)


def grant_to_out(grant: CaseAccess) -> CaseAccessOut:
    data = CaseAccessOut.model_validate(grant)
    user = grant.user
    return data.model_copy(
        update={
            "user_full_name": user.full_name if user else None,
            "user_email": user.email if user else None,
            "user_role": user.role if user else None,
        }
    )


def current_access_label(user: User, case: Case) -> str:
    if case.owner_id == user.id:
        return "owner"
    grant = next((item for item in (case.access_grants or []) if item.user_id == user.id), None)
    if grant:
        return grant.access_type
    if has_permission(user.role, Permission.CASE_READ_ALL):
        return "administrator"
    return "none"


def to_out(case: Case, user: User | None = None, include_grants: bool = False) -> CaseOut:
    data = CaseOut.model_validate(case)
    updates = {
        "latest_image": _latest_image_summary(case),
        "owner_full_name": case.owner.full_name if case.owner else None,
    }
    if user is not None:
        updates["current_access"] = current_access_label(user, case)
    if include_grants:
        updates["access_grants"] = [grant_to_out(grant) for grant in (case.access_grants or [])]
    return data.model_copy(update=updates)


def can_access_case(db: Session, user: User, case: Case) -> bool:
    if has_permission(user.role, Permission.CASE_READ_ALL):
        return True
    if case.owner_id == user.id:
        return True
    return case_repo.user_has_grant(db, case.id, user.id)


def can_manage_case_access(user: User, case: Case) -> bool:
    if has_permission(user.role, Permission.CASE_READ_ALL):
        return True
    return case.owner_id == user.id and (
        has_permission(user.role, Permission.CASE_SHARE) or has_permission(user.role, Permission.CASE_ASSIGN)
    )


def can_mutate_case(user: User, case: Case) -> bool:
    if has_permission(user.role, Permission.CASE_READ_ALL):
        return True
    return case.owner_id == user.id


def get_accessible_case(db: Session, user: User, case_id: str) -> Case:
    case = case_repo.get_by_id(db, case_id)
    if case is None or not can_access_case(db, user, case):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    return case


def create_case(db: Session, user: User, payload: CaseCreate) -> Case:
    if case_repo.get_by_identifier(db, payload.case_identifier):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case identifier already exists.")
    case = Case(**payload.model_dump(), owner_id=user.id, analysis_status="created")
    db.add(case)
    db.flush()
    record_audit(db, "case.create", actor_id=user.id, resource_type="case", resource_id=case.id)
    db.commit()
    db.refresh(case)
    return case_repo.get_by_id(db, case.id) or case


def list_cases(db: Session, user: User, search: str | None = None) -> list[Case]:
    return case_repo.list_for_user(db, user, search)


def update_case(db: Session, user: User, case: Case, payload: CaseUpdate) -> Case:
    if not can_mutate_case(user, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot update this case.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, key, value)
    record_audit(db, "case.update", actor_id=user.id, resource_type="case", resource_id=case.id)
    db.commit()
    db.refresh(case)
    return case_repo.get_by_id(db, case.id) or case


def delete_case(db: Session, user: User, case: Case) -> None:
    if not can_mutate_case(user, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this case.")
    record_audit(db, "case.delete", actor_id=user.id, resource_type="case", resource_id=case.id)
    db.delete(case)
    db.commit()


def _required_permission_for_access_type(access_type: str) -> Permission:
    if access_type == ACCESS_TYPE_ASSIGNED:
        return Permission.CASE_ASSIGN
    return Permission.CASE_SHARE


def grant_access(db: Session, actor: User, case: Case, user_id: str, access_type: str) -> CaseAccess:
    if not can_manage_case_access(actor, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage access for this case.")
    if access_type not in VALID_ACCESS_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access type must be assigned or shared.")
    required = _required_permission_for_access_type(access_type)
    if not has_permission(actor.role, required):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action.")
    if user_id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot grant yourself access.")
    if user_id == case.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The case owner already has access.")
    target = user_repo.get_by_id(db, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user was not found or is inactive.")

    existing = case_repo.get_grant(db, case.id, user_id)
    if existing:
        existing.access_type = access_type
        existing.granted_by_id = actor.id
        grant = existing
    else:
        grant = CaseAccess(
            case_id=case.id,
            user_id=target.id,
            access_type=access_type,
            granted_by_id=actor.id,
        )
        db.add(grant)
        db.flush()
    record_audit(
        db,
        "case.access_grant",
        actor_id=actor.id,
        resource_type="case",
        resource_id=case.id,
        metadata={"user_id": target.id, "access_type": access_type},
    )
    db.commit()
    db.refresh(grant)
    return case_repo.get_grant_by_id(db, grant.id) or grant


def list_access(db: Session, actor: User, case: Case) -> list[CaseAccess]:
    if not can_manage_case_access(actor, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage access for this case.")
    return case_repo.list_grants(db, case.id)


def revoke_access(db: Session, actor: User, case: Case, grant_id: str) -> None:
    if not can_manage_case_access(actor, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage access for this case.")
    grant = case_repo.get_grant_by_id(db, grant_id)
    if grant is None or grant.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access grant not found.")
    record_audit(
        db,
        "case.access_revoke",
        actor_id=actor.id,
        resource_type="case",
        resource_id=case.id,
        metadata={"user_id": grant.user_id, "access_type": grant.access_type},
    )
    db.delete(grant)
    db.commit()


def list_access_candidates(db: Session, actor: User, case: Case) -> list[AccessCandidateOut]:
    if not can_manage_case_access(actor, case):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage access for this case.")
    excluded = {actor.id, case.owner_id}
    users = [user for user in user_repo.list_active_users(db) if user.id not in excluded]
    return [AccessCandidateOut.model_validate(user) for user in users]

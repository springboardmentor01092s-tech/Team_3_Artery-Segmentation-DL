from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import Permission, has_permission
from app.models.case import Case
from app.models.case_access import CaseAccess
from app.models.user import User


def _case_load_options():
    return (
        selectinload(Case.images),
        selectinload(Case.preprocessing_runs),
        selectinload(Case.access_grants).selectinload(CaseAccess.user),
        selectinload(Case.owner),
    )


def get_by_id(db: Session, case_id: str) -> Case | None:
    return db.scalar(select(Case).options(*_case_load_options()).where(Case.id == case_id))


def get_by_identifier(db: Session, identifier: str) -> Case | None:
    return db.scalar(select(Case).where(Case.case_identifier == identifier))


def visible_scope_clause(user: User):
    if has_permission(user.role, Permission.CASE_READ_ALL):
        return None
    granted = exists().where(CaseAccess.case_id == Case.id, CaseAccess.user_id == user.id)
    return or_(Case.owner_id == user.id, granted)


def visible_case_ids(db: Session, user: User):
    stmt = select(Case.id)
    clause = visible_scope_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return stmt


def count_for_user(db: Session, user: User) -> int:
    stmt = select(func.count()).select_from(Case)
    clause = visible_scope_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return db.scalar(stmt) or 0


def list_for_user(db: Session, user: User, search: str | None = None) -> list[Case]:
    stmt = select(Case).options(*_case_load_options()).order_by(Case.created_at.desc())
    clause = visible_scope_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    if search:
        stmt = stmt.where(Case.case_identifier.ilike(f"%{search}%"))
    return list(db.scalars(stmt).unique().all())


def get_grant(db: Session, case_id: str, user_id: str) -> CaseAccess | None:
    return db.scalar(select(CaseAccess).where(CaseAccess.case_id == case_id, CaseAccess.user_id == user_id))


def get_grant_by_id(db: Session, grant_id: str) -> CaseAccess | None:
    return db.scalar(
        select(CaseAccess)
        .options(selectinload(CaseAccess.user), selectinload(CaseAccess.granted_by))
        .where(CaseAccess.id == grant_id)
    )


def list_grants(db: Session, case_id: str) -> list[CaseAccess]:
    stmt = (
        select(CaseAccess)
        .options(selectinload(CaseAccess.user), selectinload(CaseAccess.granted_by))
        .where(CaseAccess.case_id == case_id)
        .order_by(CaseAccess.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def user_has_grant(db: Session, case_id: str, user_id: str) -> bool:
    return get_grant(db, case_id, user_id) is not None

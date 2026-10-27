from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, owned_or_admin
from app.db.session import get_db
from app.models.case import Case
from app.models.patient import Patient
from app.models.user import User
from app.schemas.case import CaseCreate, CaseRead, CaseUpdate

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseRead])
def list_cases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Case]:
    query = owned_or_admin(select(Case), Case, current_user).order_by(Case.created_at.desc())
    return list(db.scalars(query).all())


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Case:
    patient = db.scalar(owned_or_admin(select(Patient), Patient, current_user).where(Patient.id == payload.patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = Case(
        owner_id=patient.owner_id,
        patient_id=patient.id,
        case_ref=payload.case_ref.strip(),
        modality=payload.modality,
    )
    db.add(case)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Case reference already exists for this owner") from exc
    db.refresh(case)
    return case


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Case:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(case_id: UUID, payload: CaseUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Case:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        # An explicitly supplied null clears nullable fields such as modality.
        # Required fields remain protected by the request schema.
        if value is not None or field == "modality":
            setattr(case, field, value.strip() if isinstance(value, str) else value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Case reference already exists for this owner") from exc
    db.refresh(case)
    return case

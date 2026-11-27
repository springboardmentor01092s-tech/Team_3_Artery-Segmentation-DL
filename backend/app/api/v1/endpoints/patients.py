from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, owned_or_admin
from app.db.session import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead])
def list_patients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[PatientRead]:
    query = (
        owned_or_admin(select(Patient, User.full_name).join(User, User.id == Patient.owner_id), Patient, current_user)
        .order_by(Patient.created_at.desc())
    )
    return [PatientRead.model_validate(patient).model_copy(update={"owner_name": owner_name}) for patient, owner_name in db.execute(query)]


def patient_read(db: Session, patient: Patient) -> PatientRead:
    owner_name = db.scalar(select(User.full_name).where(User.id == patient.owner_id))
    return PatientRead.model_validate(patient).model_copy(update={"owner_name": owner_name})


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PatientRead:
    owner_id = payload.owner_id or current_user.id
    if current_user.role != "admin" and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot create records for another user")
    if db.get(User, owner_id) is None:
        raise HTTPException(status_code=404, detail="Owner not found")
    patient = Patient(owner_id=owner_id, patient_ref=payload.patient_ref.strip())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient reference already exists for this owner") from exc
    db.refresh(patient)
    return patient_read(db, patient)


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PatientRead:
    patient = db.scalar(owned_or_admin(select(Patient), Patient, current_user).where(Patient.id == patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient_read(db, patient)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: UUID, payload: PatientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> PatientRead:
    patient = db.scalar(owned_or_admin(select(Patient), Patient, current_user).where(Patient.id == patient_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.patient_ref = payload.patient_ref.strip()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient reference already exists for this owner") from exc
    db.refresh(patient)
    return patient_read(db, patient)

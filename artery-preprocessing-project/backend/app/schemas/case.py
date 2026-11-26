from datetime import date, datetime

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    case_identifier: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    patient_identifier: str = Field(min_length=2, max_length=64)
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = Field(default=None, max_length=32)
    medical_history: str | None = Field(default=None, max_length=4000)
    risk_factors: str | None = Field(default=None, max_length=2000)
    clinical_notes: str | None = Field(default=None, max_length=4000)
    imaging_modality: str = Field(min_length=2, max_length=64)
    scan_date: date | None = None
    anatomical_region: str | None = Field(default=None, max_length=80)


class CaseUpdate(BaseModel):
    patient_identifier: str | None = Field(default=None, min_length=2, max_length=64)
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = Field(default=None, max_length=32)
    medical_history: str | None = Field(default=None, max_length=4000)
    risk_factors: str | None = Field(default=None, max_length=2000)
    clinical_notes: str | None = Field(default=None, max_length=4000)
    imaging_modality: str | None = Field(default=None, min_length=2, max_length=64)
    scan_date: date | None = None
    anatomical_region: str | None = Field(default=None, max_length=80)


class ImageSummary(BaseModel):
    id: str
    original_filename: str
    format: str
    file_size: int
    width: int | None
    height: int | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class CaseAccessGrant(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)
    access_type: str = Field(pattern=r"^(assigned|shared)$")


class CaseAccessOut(BaseModel):
    id: str
    case_id: str
    user_id: str
    access_type: str
    granted_by_id: str
    created_at: datetime
    user_full_name: str | None = None
    user_email: str | None = None
    user_role: str | None = None

    model_config = {"from_attributes": True}


class AccessCandidateOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: str
    case_identifier: str
    patient_identifier: str
    age: int | None
    gender: str | None
    medical_history: str | None
    risk_factors: str | None
    clinical_notes: str | None
    imaging_modality: str
    scan_date: date | None
    anatomical_region: str | None
    analysis_status: str
    model_version: str | None
    owner_id: str
    owner_full_name: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_image: ImageSummary | None = None
    current_access: str | None = None
    access_grants: list[CaseAccessOut] | None = None

    model_config = {"from_attributes": True}

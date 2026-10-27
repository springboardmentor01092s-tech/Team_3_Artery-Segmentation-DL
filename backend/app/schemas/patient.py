from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    patient_ref: str = Field(min_length=1, max_length=100)
    owner_id: UUID | None = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    patient_ref: str = Field(min_length=1, max_length=100)


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    patient_ref: str
    created_at: datetime

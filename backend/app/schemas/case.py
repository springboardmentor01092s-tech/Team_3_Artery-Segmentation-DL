from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    patient_id: UUID
    case_ref: str = Field(min_length=1, max_length=100)
    modality: str | None = Field(default=None, max_length=50)


class CaseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case_ref: str | None = Field(default=None, min_length=1, max_length=100)
    modality: str | None = Field(default=None, max_length=50)


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    patient_id: UUID
    case_ref: str
    modality: str | None
    created_at: datetime

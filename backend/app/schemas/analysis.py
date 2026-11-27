from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalysisRunCreate(BaseModel):
    image_id: UUID


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    image_id: UUID | None
    requested_by_id: UUID
    status: Literal["unavailable", "queued", "processing", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    result_metadata: dict[str, Any] | None
    failure_code: str | None
    failure_message: str | None


class AnalysisUnavailable(BaseModel):
    code: Literal["analysis_unavailable"] = "analysis_unavailable"
    detail: str = "No inference model is configured. No analysis was run and no results were generated."

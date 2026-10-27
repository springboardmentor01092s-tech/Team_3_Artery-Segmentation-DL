from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    requested_by_id: UUID
    status: Literal["unavailable", "queued", "processing", "completed", "failed"]
    created_at: datetime
    completed_at: datetime | None


class AnalysisUnavailable(BaseModel):
    code: Literal["analysis_unavailable"] = "analysis_unavailable"
    detail: str = "No inference model is configured. No analysis was run and no results were generated."

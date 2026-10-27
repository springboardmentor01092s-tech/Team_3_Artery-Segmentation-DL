from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PreprocessingMetadata(BaseModel):
    input_width: int
    input_height: int
    source_mode: str
    output_width: int
    output_height: int
    output_shape: list[int]
    model_batch_shape: list[int]
    data_type: str
    channel_format: str
    intensity_range: list[float]
    normalization: str
    resize: str
    output_persisted: bool


class PreprocessingRead(BaseModel):
    image_id: UUID
    status: Literal["not_started", "completed", "failed"]
    message: str
    attempt_count: int
    updated_at: datetime | None = None
    result: PreprocessingMetadata | None = None

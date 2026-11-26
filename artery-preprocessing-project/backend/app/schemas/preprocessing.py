from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PreprocessRequest(BaseModel):
    normalize: bool = True
    normalize_method: Literal["minmax", "zscore", "none"] = "minmax"
    resize: bool = False
    target_width: int | None = Field(default=512, ge=32, le=2048)
    target_height: int | None = Field(default=512, ge=32, le=2048)
    preserve_aspect_ratio: bool = True
    denoise: bool = False
    denoise_method: Literal["gaussian", "median", "none"] = "gaussian"
    denoise_ksize: int = Field(default=3, ge=3, le=9)
    contrast: bool = False
    contrast_method: Literal["clahe", "none"] = "clahe"
    clahe_clip_limit: float = Field(default=2.0, ge=1.0, le=8.0)
    clahe_tile_size: int = Field(default=8, ge=2, le=16)


class PreprocessingRunOut(BaseModel):
    id: str
    case_id: str
    image_id: str
    config_json: str
    processed_storage_filename: str | None
    input_format: str
    original_width: int | None
    original_height: int | None
    processed_width: int | None
    processed_height: int | None
    operations_json: str
    status: str
    error_message: str | None
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    initiated_by_id: str

    model_config = {"from_attributes": True}


class DatasetSourceSummary(BaseModel):
    directory: str
    exists: bool
    supported_count: int
    unreadable_count: int
    formats: dict[str, int]
    note: str


class ArcadeSplitSummary(BaseModel):
    directory: str
    exists: bool
    image_count: int
    annotation_status: str
    annotation_image_count: int | None
    annotation_count: int | None
    category_ids: list[int]
    selection_eligible: bool
    note: str
    annotation_file: str | None = None


class ArcadeDatasetSummary(BaseModel):
    root: str
    exists: bool
    tasks: dict[str, dict[str, ArcadeSplitSummary]]


class DatasetSummary(BaseModel):
    directory: str
    exists: bool
    supported_count: int
    unreadable_count: int
    formats: dict[str, int]
    note: str
    sample_supported_count: int
    uploaded_supported_count: int
    sample: DatasetSourceSummary
    uploaded: DatasetSourceSummary
    arcade: ArcadeDatasetSummary

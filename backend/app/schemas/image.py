from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    created_at: datetime

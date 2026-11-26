from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import UserRole


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class AdminUserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: str
    actor_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    metadata_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    case_count: int
    image_count: int
    preprocessing_count: int
    user_count: int | None = None
    failed_preprocessing_count: int = 0
    segmentation_analysis_count: int = 0
    processed_case_count: int = 0
    pending_case_count: int = 0
    role: UserRole
    disclaimer: str = Field(
        default="Segmentation outputs are research predictions. Severity and percentage narrowing are not reported without validated diameter measurements."
    )

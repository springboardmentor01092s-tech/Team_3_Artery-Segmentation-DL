from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import Permission, UserRole, has_permission
from app.models.image import UploadedImage
from app.models.analysis import StenosisAnalysis
from app.models.case import Case
from app.models.preprocessing import PreprocessingRun
from app.models.user import User
from app.repositories import cases as case_repo
from app.schemas.admin import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible_ids = case_repo.visible_case_ids(db, user)
    case_count = case_repo.count_for_user(db, user)
    image_count = db.scalar(select(func.count(UploadedImage.id)).where(UploadedImage.case_id.in_(visible_ids))) or 0
    preprocessing_count = (
        db.scalar(select(func.count(PreprocessingRun.id)).where(PreprocessingRun.case_id.in_(visible_ids))) or 0
    )
    failed = (
        db.scalar(
            select(func.count(PreprocessingRun.id)).where(
                PreprocessingRun.case_id.in_(visible_ids), PreprocessingRun.status == "failed"
            )
        )
        or 0
    )
    analysis_count = db.scalar(select(func.count(StenosisAnalysis.id)).where(StenosisAnalysis.case_id.in_(visible_ids))) or 0
    processed_case_count = db.scalar(select(func.count(func.distinct(PreprocessingRun.case_id))).where(
        PreprocessingRun.case_id.in_(visible_ids), PreprocessingRun.status == "completed")) or 0
    pending_case_count = db.scalar(select(func.count(Case.id)).where(
        Case.id.in_(visible_ids), Case.analysis_status.notin_(["preprocessed", "segmentation_completed"]))) or 0
    user_count = None
    if has_permission(user.role, Permission.USER_MANAGE):
        user_count = db.scalar(select(func.count(User.id))) or 0
    return DashboardStats(
        case_count=case_count,
        image_count=image_count,
        preprocessing_count=preprocessing_count,
        failed_preprocessing_count=failed,
        segmentation_analysis_count=analysis_count,
        processed_case_count=processed_case_count,
        pending_case_count=pending_case_count,
        user_count=user_count,
        role=UserRole(user.role),
    )

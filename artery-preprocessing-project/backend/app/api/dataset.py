from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.preprocessing import DatasetSummary
from app.services.dataset_service import summarize_dataset

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


@router.get("/summary", response_model=DatasetSummary)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.DATASET_INSPECT)),
):
    return summarize_dataset(db, user)

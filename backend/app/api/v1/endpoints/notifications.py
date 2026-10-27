from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc())
    return list(db.scalars(query).all())

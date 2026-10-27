import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImagePreprocessing(Base):
    """Latest preprocessing attempt metadata for one stored image."""

    __tablename__ = "image_preprocessing"
    __table_args__ = (
        CheckConstraint("status IN ('completed', 'failed')", name="ck_image_preprocessing_status"),
        CheckConstraint("attempt_count >= 1", name="ck_image_preprocessing_attempt_count"),
    )

    image_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("medical_images.id", ondelete="CASCADE"), primary_key=True
    )
    preprocessed_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    result_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

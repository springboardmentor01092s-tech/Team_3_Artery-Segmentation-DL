import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class PreprocessingRun(Base):
    __tablename__ = "preprocessing_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    image_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_images.id"), nullable=False, index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    processed_storage_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_format: Mapped[str] = mapped_column(String(32), nullable=False)
    original_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operations_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initiated_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    case: Mapped["Case"] = relationship(back_populates="preprocessing_runs")  # noqa: F821
    image: Mapped["UploadedImage"] = relationship(back_populates="preprocessing_runs")  # noqa: F821
    initiated_by: Mapped["User"] = relationship()  # noqa: F821

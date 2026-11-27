import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisRun(Base):
    """Persisted synchronous analysis request and safe result metadata."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unavailable', 'queued', 'processing', 'completed', 'failed')",
            name="ck_analysis_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    image_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("medical_images.id", ondelete="CASCADE"), index=True, nullable=True
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unavailable")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

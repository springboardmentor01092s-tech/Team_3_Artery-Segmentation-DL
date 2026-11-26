
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_identifier: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    patient_identifier: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    age: Mapped[int | None] = mapped_column(nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    imaging_modality: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    anatomical_region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(40), default="created", index=True)
    model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="cases")  # noqa: F821
    images: Mapped[list["UploadedImage"]] = relationship(  # noqa: F821
        back_populates="case", cascade="all, delete-orphan"
    )
    preprocessing_runs: Mapped[list["PreprocessingRun"]] = relationship(  # noqa: F821
        back_populates="case", cascade="all, delete-orphan"
    )
    access_grants: Mapped[list["CaseAccess"]] = relationship(  # noqa: F821
        back_populates="case", cascade="all, delete-orphan"
    )
    stenosis_analyses: Mapped[list["StenosisAnalysis"]] = relationship(  # noqa: F821
        back_populates="case", cascade="all, delete-orphan"
    )

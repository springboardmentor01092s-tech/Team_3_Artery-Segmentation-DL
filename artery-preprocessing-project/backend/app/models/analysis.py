import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class StenosisAnalysis(Base):
    __tablename__ = "stenosis_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    image_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_images.id"), index=True)
    initiated_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_architecture: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="completed")
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="stenosis_analyses")  # noqa: F821
    image: Mapped["UploadedImage"] = relationship()  # noqa: F821
    initiated_by: Mapped["User"] = relationship()  # noqa: F821

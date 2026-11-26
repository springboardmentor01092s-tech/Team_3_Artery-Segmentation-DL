import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class CaseAccess(Base):
    __tablename__ = "case_access"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_access_case_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    access_type: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="access_grants")  # noqa: F821
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="received_case_access")  # noqa: F821
    granted_by: Mapped["User"] = relationship(foreign_keys=[granted_by_id], back_populates="granted_case_access")  # noqa: F821

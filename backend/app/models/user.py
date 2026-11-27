import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Uuid, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

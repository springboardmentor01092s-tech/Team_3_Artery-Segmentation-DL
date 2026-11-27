from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "user"] = "user"

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserRoleUpdate(BaseModel):
    role: Literal["admin", "user"]


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserPasswordReset(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_profile_fields(self) -> "ProfileUpdate":
        supplied = self.model_fields_set
        if not supplied:
            raise ValueError("Provide at least one profile field to update")
        if "full_name" in supplied and self.full_name is None:
            raise ValueError("Full name cannot be null")
        if "email" in supplied and self.email is None:
            raise ValueError("Email cannot be null")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None
    email: EmailStr
    role: Literal["admin", "user"]
    is_active: bool
    must_change_password: bool = False
    created_at: datetime


class ProfileUpdateRead(UserRead):
    email_verification_sent: bool = False


class EmailChangeVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class EmailChangeVerificationRead(BaseModel):
    detail: str


class UserDeletionRead(BaseModel):
    deleted_user_id: UUID
    cleanup_status: Literal["complete", "pending"]
    cleanup_id: UUID | None
    detail: str


class UserDeletionCleanupRead(BaseModel):
    cleanup_id: UUID
    created_at: str | None
    storage_file_count: int
    analysis_run_count: int
    last_error: str | None


class UserDeletionRetryRead(BaseModel):
    cleanup_id: UUID
    status: Literal["complete", "pending", "not_deleted"]
    detail: str

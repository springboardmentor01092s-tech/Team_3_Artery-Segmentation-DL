from pydantic import BaseModel, EmailStr, Field, computed_field

from app.core.permissions import UserRole, permissions_for_role


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}

    @computed_field
    def permissions(self) -> list[str]:
        return permissions_for_role(self.role)


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)

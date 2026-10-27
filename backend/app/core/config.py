from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
    env_file=str(Path(__file__).resolve().parents[2] / ".env"),
    env_file_encoding="utf-8",
    extra="ignore",
)

    environment: str = "development"
    postgres_db: str = "artery_local"
    postgres_user: str = "artery_local"
    postgres_password: SecretStr = SecretStr("")
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    database_url: str | None = None
    secret_key: SecretStr = SecretStr("")
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    max_image_pixels: int = Field(default=40_000_000, ge=1, le=100_000_000)
    upload_directory: Path = Path("./storage/uploads")

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        cleaned = [origin.strip().rstrip("/") for origin in origins if origin.strip()]
        if not cleaned:
            raise ValueError("At least one CORS origin must be configured")
        return cleaned

    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        password = self.postgres_password.get_secret_value()
        if not password:
            raise RuntimeError("POSTGRES_PASSWORD must be set in backend/.env")
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

    def signing_key(self) -> str:
        key = self.secret_key.get_secret_value()
        if len(key.encode("utf-8")) < 32:
            raise RuntimeError("SECRET_KEY must contain at least 32 bytes")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()

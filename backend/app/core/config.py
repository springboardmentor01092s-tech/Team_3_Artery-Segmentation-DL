from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field, SecretStr, field_validator
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
    analysis_output_directory: Path = Path(__file__).resolve().parents[2] / "storage" / "analysis"
    attention_checkpoint_path: Path | None = None
    unetpp_checkpoint_path: Path | None = None
    analysis_stenosis_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    analysis_min_component_area: int = Field(default=5, ge=1)
    analysis_cpu_threads: int = Field(default=2, ge=1, le=32)
    ml_python_executable: Path = Path(__file__).resolve().parents[3] / "ml" / ".venv" / "Scripts" / "python.exe"
    analysis_timeout_seconds: int = Field(default=600, ge=10, le=3600)
    analysis_worker_startup_timeout_seconds: int = Field(default=600, ge=10, le=1800)
    analysis_max_response_bytes: int = Field(default=512 * 1024 * 1024, ge=1_048_576, le=1024 * 1024 * 1024)
    login_rate_limit_attempts: int = Field(default=10, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=900, ge=30, le=86_400)
    email_verification_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    email_verification_frontend_url: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr = SecretStr("")
    smtp_from_email: EmailStr | None = None
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True

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

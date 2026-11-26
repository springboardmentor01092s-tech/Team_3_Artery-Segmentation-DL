from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Artery Image Preprocessing System"
    app_env: str = "development"
    secret_key: str = Field(default="dev-only-change-me-before-any-shared-use")
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    database_url: str = "sqlite:///./artery_preprocessing.db"

    upload_dir: str = "./uploads"
    processed_dir: str = "./processed"
    analysis_dir: str = "./analysis"
    model_checkpoint: str = "./checkpoints/best_stenosis_unet_optimized.pth"
    arcade_root: str | None = None
    dataset_dir: str = "../data/sample_images"

    max_upload_bytes: int = 20 * 1024 * 1024
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_file: str = "./logs/artery-preprocessing.log"
    log_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=1024 * 1024 * 1024)
    log_backup_count: int = Field(default=5, ge=0, le=20)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value):
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.strip().lower() in {"prod", "production"}:
            if (
                len(self.secret_key) < 32
                or self.secret_key == "dev-only-change-me-before-any-shared-use"
                or self.secret_key == "replace-with-a-long-random-secret-before-use"
            ):
                raise ValueError("Production requires a non-default SECRET_KEY with at least 32 characters.")
            origins = self.origin_list()
            if not origins or "*" in origins:
                raise ValueError("Production requires explicit ALLOWED_ORIGINS and does not allow '*'.")
            for origin in origins:
                parsed = urlsplit(origin)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Production ALLOWED_ORIGINS must contain HTTPS origins without local hosts or paths.")
        return self

    def sqlite_connect_args(self) -> dict:
        if self.database_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}

    def origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    def resolved_upload_dir(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    def resolved_processed_dir(self) -> Path:
        path = Path(self.processed_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    def resolved_analysis_dir(self) -> Path:
        path = Path(self.analysis_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    def resolved_checkpoint_path(self) -> Path:
        path = Path(self.model_checkpoint)
        return path if path.is_absolute() else BACKEND_DIR / path

    def resolved_arcade_root(self) -> Path:
        if not self.arcade_root:
            return BACKEND_DIR.parent.parent
        path = Path(self.arcade_root)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    def resolved_dataset_dir(self) -> Path:
        path = Path(self.dataset_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    def resolved_log_file(self) -> Path:
        path = Path(self.log_file).expanduser()
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()

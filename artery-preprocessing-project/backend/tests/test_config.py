import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_development_secret():
    with pytest.raises(ValidationError, match="Production requires a non-default SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="dev-only-change-me-before-any-shared-use",
            allowed_origins="https://app.example.org",
        )


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            app_env="prod",
            secret_key="too-short",
            allowed_origins="https://app.example.org",
        )


def test_production_rejects_example_secret_placeholder():
    with pytest.raises(ValidationError, match="non-default SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="replace-with-a-long-random-secret-before-use",
            allowed_origins="https://app.example.org",
        )


@pytest.mark.parametrize("origins", ["", "*"])
def test_production_requires_explicit_non_wildcard_origins(origins):
    with pytest.raises(ValidationError, match="explicit ALLOWED_ORIGINS"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="a-strong-production-secret-key-0123456789",
            allowed_origins=origins,
        )


@pytest.mark.parametrize("origins", ["http://app.example.org", "https://localhost:5173"])
def test_production_rejects_insecure_or_local_origins(origins):
    with pytest.raises(ValidationError, match="HTTPS origins"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="a-strong-production-secret-key-0123456789",
            allowed_origins=origins,
        )


def test_production_accepts_explicit_https_origin():
    settings = Settings(
        _env_file=None,
        app_env="production",
        secret_key="a-strong-production-secret-key-0123456789",
        allowed_origins="https://artery.example.org",
    )
    assert settings.origin_list() == ["https://artery.example.org"]


def test_development_defaults_remain_available():
    settings = Settings(
        _env_file=None,
        app_env="development",
        secret_key="dev-only-change-me-before-any-shared-use",
    )
    assert settings.app_env == "development"
    assert settings.secret_key == "dev-only-change-me-before-any-shared-use"

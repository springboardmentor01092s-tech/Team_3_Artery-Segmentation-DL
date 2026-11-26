import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.limiter import limiter

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.core.config import get_settings
from app.database.base import Base
from app.core.limiter import limiter
from app.database.session import get_db
from app.main import app
from app.models import Case, CaseAccess, User  # noqa: F401
from app.security.passwords import hash_password
from app.core.permissions import UserRole

@pytest.fixture(autouse=True)
def disable_rate_limit_during_tests(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)


@pytest.fixture
def storage_dirs(tmp_path, monkeypatch):
    upload = tmp_path / "uploads"
    processed = tmp_path / "processed"
    dataset = tmp_path / "dataset"
    arcade = tmp_path / "arcade"
    upload.mkdir()
    processed.mkdir()
    dataset.mkdir()
    arcade.mkdir()
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(upload))
    monkeypatch.setenv("PROCESSED_DIR", str(processed))
    monkeypatch.setenv("DATASET_DIR", str(dataset))
    monkeypatch.setenv("ARCADE_ROOT", str(arcade))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    get_settings.cache_clear()
    return {"upload": upload, "processed": processed, "dataset": dataset, "arcade": arcade}


@pytest.fixture
def db_session(storage_dirs):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session, storage_dirs, monkeypatch):
    # Startup should never create or modify the developer's configured database during tests.
    monkeypatch.setattr("app.main.init_db", lambda: None)
    # Keep application startup from creating files at the developer's configured log path.
    # Logging behavior itself is tested with isolated temporary directories.
    monkeypatch.setattr("app.main.configure_logging", lambda _settings: None)
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def png_bytes():
    buf = io.BytesIO()
    Image.new("L", (64, 64), color=80).save(buf, format="PNG")
    return buf.getvalue()


def register_and_login(client: TestClient, email: str, password: str = "Password123", name: str = "Test User"):
    res = client.post("/api/auth/register", json={"full_name": name, "email": email, "password": password})
    assert res.status_code == 201, res.text
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return token, res.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user(db_session, email: str, role: str, password: str = "Password123"):
    from app.models.user import User

    user = User(
        full_name=email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

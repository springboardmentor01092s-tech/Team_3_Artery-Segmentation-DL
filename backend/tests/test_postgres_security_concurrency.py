"""Concurrency checks that run only in the dedicated, isolated security-test DB."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401 - register all ORM tables on Base.metadata
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_DATABASE = "coronai_security_test"
EXPECTED_USER = "coronai_security_test"
EXPECTED_PORT = 55433


@pytest.fixture
def isolated_postgres_security_db():
    raw_url = os.environ.get("CORONAI_SECURITY_TEST_DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip("Set CORONAI_SECURITY_TEST_DATABASE_URL for the dedicated PostgreSQL concurrency database")

    try:
        url = make_url(raw_url)
    except Exception:
        pytest.fail("The dedicated PostgreSQL test database URL is invalid; it was not used")
    if (
        url.drivername not in {"postgresql+psycopg", "postgresql"}
        or url.host not in EXPECTED_HOSTS
        or url.port != EXPECTED_PORT
        or url.database != EXPECTED_DATABASE
        or url.username != EXPECTED_USER
    ):
        pytest.fail("Refusing PostgreSQL concurrency test: URL is not the dedicated loopback security-test database")

    schema = f"m4_security_{uuid.uuid4().hex}"
    root_engine = create_engine(url, pool_pre_ping=True, pool_size=6, max_overflow=0)
    scoped_engine = None
    previous_override = app.dependency_overrides.get(get_db)
    schema_created = False
    try:
        with root_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        scoped_engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema}"},
            pool_pre_ping=True,
            pool_size=6,
            max_overflow=0,
        )
        Base.metadata.create_all(scoped_engine)
        test_session = sessionmaker(bind=scoped_engine, expire_on_commit=False)

        def override_get_db():
            with test_session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        yield test_session
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        if scoped_engine is not None:
            Base.metadata.drop_all(scoped_engine)
            scoped_engine.dispose()
        if schema_created:
            with root_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root_engine.dispose()


@pytest.mark.parametrize("action", ["role", "status"])
def test_concurrent_admin_changes_preserve_last_active_admin(isolated_postgres_security_db, action):
    test_session = isolated_postgres_security_db
    with test_session() as db:
        first = User(email=f"security-a-{action}@example.test", password_hash=hash_password("synthetic-admin-password-a"), role="admin")
        second = User(email=f"security-b-{action}@example.test", password_hash=hash_password("synthetic-admin-password-b"), role="admin")
        db.add_all([first, second])
        db.commit()
        first_id, second_id = first.id, second.id
        first_token = create_access_token(first.id, first.token_version)
        second_token = create_access_token(second.id, second.token_version)

    barrier = threading.Barrier(2)

    def change_account(target_id, token):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            if action == "role":
                return client.patch(
                    f"/api/v1/users/{target_id}/role",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"role": "user"},
                ).status_code
            return client.patch(
                f"/api/v1/users/{target_id}/status",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_active": False},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(
            lambda args: change_account(*args),
            [(second_id, first_token), (first_id, second_token)],
        ))

    assert all(code in {200, 409} for code in outcomes)
    with test_session() as db:
        remaining = db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True)))
        assert remaining >= 1

import hashlib
import io
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Depends, Request

os.environ.setdefault("SECRET_KEY", "local-test-signing-key-not-for-production-123456")
os.environ.setdefault("POSTGRES_PASSWORD", "local-test-password")

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_authenticated_user
from app.api.v1.endpoints import auth as auth_endpoints
from app.api.v1.endpoints import images as image_endpoints, preprocessing as preprocessing_endpoints, users as user_endpoints
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.case import Case
from app.models.analysis_run import AnalysisRun
from app.models.image_preprocessing import ImagePreprocessing
from app.models.image import MedicalImage
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.security_state import EmailChangeVerification, LoginRateLimitBucket
from app.models.user import User
from app.schemas.user import UserPasswordReset
from app.services import user_deletion as user_deletion_service


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), color=(120, 120, 120)).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def isolated_api_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), test_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_health_api_reports_database_ready(isolated_api_client):
    client, _ = isolated_api_client

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_api_reports_database_unavailable(isolated_api_client):
    client, _ = isolated_api_client

    class UnavailableDatabase:
        def execute(self, _statement):
            raise RuntimeError("synthetic database unavailable")

    def override_unavailable_db():
        yield UnavailableDatabase()

    app.dependency_overrides[get_db] = override_unavailable_db
    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}


def test_user_creation_requires_admin_and_returns_no_password(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="api-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        regular = User(email="api-user@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add_all([admin, regular])
        db.commit()
        admin_token, regular_token = create_access_token(admin.id), create_access_token(regular.id)

    payload = {"full_name": "  New Test User  ", "email": "new-user@example.com", "password": "synthetic-new-password", "role": "user"}
    created = client.post("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"}, json=payload)

    assert created.status_code == 201, created.text
    created_data = created.json()
    assert created_data["full_name"] == "New Test User"
    assert created_data["email"] == payload["email"]
    assert created_data["role"] == "user"
    assert "password" not in created_data
    assert "password_hash" not in created_data
    with test_session() as db:
        stored_user = db.scalar(select(User).where(User.email == payload["email"]))
        assert stored_user is not None
        assert stored_user.password_hash != payload["password"]
        assert verify_password(payload["password"], stored_user.password_hash)

    admin_payload = {"full_name": "Second Test Admin", "email": "second-admin@example.com", "password": "synthetic-admin-password", "role": "admin"}
    created_admin = client.post("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"}, json=admin_payload)
    assert created_admin.status_code == 201, created_admin.text
    assert created_admin.json()["role"] == "admin"
    assert created_admin.json()["full_name"] == "Second Test Admin"

    forbidden = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {regular_token}"},
        json={"full_name": "Forbidden User", "email": "forbidden-user@example.com", "password": "synthetic-new-password", "role": "user"},
    )
    assert forbidden.status_code == 403


def test_user_creation_rejects_duplicate_email_and_invalid_input(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="duplicate-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        existing = User(email="existing-user@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add_all([admin, existing])
        db.commit()
        admin_token = create_access_token(admin.id)

    headers = {"Authorization": f"Bearer {admin_token}"}
    duplicate = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "Duplicate User", "email": "EXISTING-USER@example.com", "password": "synthetic-new-password", "role": "user"},
    )
    assert duplicate.status_code == 409

    invalid = client.post(
        "/api/v1/users",
        headers=headers,
        json={"full_name": "Invalid User", "email": "not-an-email", "password": "short", "role": "unsupported"},
    )
    assert invalid.status_code == 422


def test_user_listing_authentication_and_legacy_user_defaults(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="list-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        regular = User(email="legacy-user@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add_all([admin, regular])
        db.commit()
        admin_token, regular_token = create_access_token(admin.id), create_access_token(regular.id)

    assert client.get("/api/v1/users").status_code == 401
    assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {regular_token}"}).status_code == 403
    listed = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})

    assert listed.status_code == 200
    legacy_user = next(item for item in listed.json() if item["email"] == "legacy-user@example.com")
    assert legacy_user["full_name"] is None
    assert legacy_user["must_change_password"] is False
    assert "password" not in legacy_user
    assert "password_hash" not in legacy_user


@pytest.mark.parametrize("full_name", ["", "   ", "x" * 121])
def test_user_creation_rejects_invalid_full_name(isolated_api_client, full_name):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="name-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        db.add(admin)
        db.commit()
        token = create_access_token(admin.id)

    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": full_name, "email": "named-user@example.com", "password": "synthetic-new-password", "role": "user"},
    )
    assert response.status_code == 422


def test_user_role_management_and_last_active_admin_safeguards(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="role-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        regular = User(email="role-user@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add_all([admin, regular])
        db.commit()
        admin_id, regular_id = admin.id, regular.id
        admin_token, regular_token = create_access_token(admin.id), create_access_token(regular.id)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    regular_headers = {"Authorization": f"Bearer {regular_token}"}
    url = f"/api/v1/users/{regular_id}/role"
    assert client.patch(url, headers=regular_headers, json={"role": "admin"}).status_code == 403
    assert client.patch(url, headers=admin_headers, json={"role": "unsupported"}).status_code == 422
    promoted = client.patch(url, headers=admin_headers, json={"role": "admin"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    # With two active administrators, one can be demoted while preserving the other.
    self_demoted = client.patch(f"/api/v1/users/{admin_id}/role", headers=admin_headers, json={"role": "user"})
    assert self_demoted.status_code == 200
    assert self_demoted.json()["role"] == "user"

    remaining_admin_headers = {"Authorization": f"Bearer {regular_token}"}
    last_admin_demotion = client.patch(url, headers=remaining_admin_headers, json={"role": "user"})
    assert last_admin_demotion.status_code == 409


def test_user_status_management_preserves_records_and_protects_last_admin(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="status-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        second_admin = User(
            email="status-second-admin@example.com",
            password_hash=hash_password("synthetic-password-second-admin"),
            role="admin",
        )
        owner = User(email="status-owner@example.com", password_hash=hash_password("synthetic-password-owner"), role="user")
        db.add_all([admin, second_admin, owner])
        db.flush()
        patient = Patient(owner_id=owner.id, patient_ref="synthetic-status-patient")
        db.add(patient)
        db.flush()
        case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="synthetic-status-case")
        db.add(case)
        db.flush()
        image_model = MedicalImage(
            case_id=case.id,
            uploaded_by_id=owner.id,
            storage_key="synthetic-status-image.png",
            original_filename="synthetic-status-image.png",
            media_type="image/png",
            size_bytes=1,
            sha256="0" * 64,
        )
        db.add(image_model)
        db.commit()
        admin_id, owner_id, patient_id, case_id, image_id = admin.id, owner.id, patient.id, case.id, image_model.id
        admin_token, owner_token = create_access_token(admin.id), create_access_token(owner.id)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    status_url = f"/api/v1/users/{owner_id}/status"
    assert client.patch(status_url, headers=owner_headers, json={"is_active": False}).status_code == 403
    assert client.patch(f"/api/v1/users/{admin_id}/status", headers=admin_headers, json={"is_active": False}).status_code == 409

    deactivated = client.patch(status_url, headers=admin_headers, json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "status-owner@example.com", "password": "synthetic-password-owner"},
    ).status_code == 401
    assert client.get("/api/v1/patients", headers=owner_headers).status_code == 401

    with test_session() as db:
        assert db.get(Patient, patient_id) is not None
        assert db.get(Case, case_id) is not None
        assert db.get(MedicalImage, image_id) is not None

    reactivated = client.patch(status_url, headers=admin_headers, json={"is_active": True})
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "status-owner@example.com", "password": "synthetic-password-owner"},
    ).status_code == 200


def test_temporary_password_reset_and_forced_change_flow(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="reset-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        target = User(email="reset-target@example.com", password_hash=hash_password("synthetic-password-old"), role="user")
        regular = User(email="reset-regular@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add_all([admin, target, regular])
        db.commit()
        admin_id, target_id, regular_id = admin.id, target.id, regular.id
        admin_token = create_access_token(admin.id)
        target_token = create_access_token(target.id)
        regular_token = create_access_token(regular.id)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    target_headers = {"Authorization": f"Bearer {target_token}"}
    regular_headers = {"Authorization": f"Bearer {regular_token}"}
    reset_url = f"/api/v1/users/{target_id}/password-reset"
    denied = client.post(reset_url, headers=regular_headers, json={"temporary_password": "synthetic-temp-password"})
    assert denied.status_code == 403
    assert client.post(reset_url, headers=admin_headers, json={"temporary_password": "short"}).status_code == 422

    reset = client.post(reset_url, headers=admin_headers, json={"temporary_password": "synthetic-temp-password"})
    assert reset.status_code == 200
    reset_data = reset.json()
    assert reset_data["must_change_password"] is True
    assert "password" not in reset_data and "password_hash" not in reset_data
    with test_session() as db:
        target = db.get(User, target_id)
        assert target is not None and target.must_change_password
        assert target.token_version == 1
        assert target.password_hash != "synthetic-temp-password"
        assert verify_password("synthetic-temp-password", target.password_hash)

    assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    temp_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset-target@example.com", "password": "synthetic-temp-password"},
    )
    assert temp_login.status_code == 200
    temp_token = temp_login.json()["access_token"]
    temp_headers = {"Authorization": f"Bearer {temp_token}"}
    second_session_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset-target@example.com", "password": "synthetic-temp-password"},
    )
    second_session_headers = {"Authorization": f"Bearer {second_session_login.json()['access_token']}"}

    current_user = client.get("/api/v1/auth/me", headers=temp_headers)
    assert current_user.status_code == 200
    assert current_user.json()["must_change_password"] is True
    restricted = client.get("/api/v1/patients", headers=temp_headers)
    assert restricted.status_code == 403
    assert restricted.json()["detail"]["code"] == "password_change_required"
    assert client.post(
        "/api/v1/auth/change-password",
        headers=temp_headers,
        json={"current_password": "wrong-temporary-password", "new_password": "synthetic-new-secure-password"},
    ).status_code == 400

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=temp_headers,
        json={"current_password": "synthetic-temp-password", "new_password": "synthetic-new-secure-password"},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert "password" not in changed.json() and "password_hash" not in changed.json()
    assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=temp_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second_session_headers).status_code == 401
    assert client.get("/api/v1/patients", headers=temp_headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "reset-target@example.com", "password": "synthetic-temp-password"},
    ).status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset-target@example.com", "password": "synthetic-new-secure-password"},
    )
    assert new_login.status_code == 200
    new_session_headers = {"Authorization": f"Bearer {new_login.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_session_headers).json()["must_change_password"] is False
    assert client.get("/api/v1/patients", headers=new_session_headers).status_code == 200

    # Keep local ids referenced to ensure the fixture is exercising distinct actors.
    assert admin_id != target_id != regular_id


def test_user_management_migration_is_chained_and_legacy_defaults_are_safe():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    previous = scripts.get_revision("0005_user_token_version")
    migration = scripts.get_revision("0006_security_controls")
    assert previous is not None
    assert migration is not None
    assert previous.down_revision == "0004_user_management"
    assert migration.down_revision == "0005_user_token_version"
    assert scripts.get_current_head() == "0006_security_controls"

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with test_session() as db:
            legacy = User(email="migration-legacy@example.com", password_hash=hash_password("synthetic-password-legacy"), role="user")
            db.add(legacy)
            db.commit()
            db.refresh(legacy)
            assert legacy.full_name is None
            assert legacy.must_change_password is False
            assert legacy.token_version == 0
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_authentication_rejects_missing_and_invalid_token_versions(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        user = User(email="token-version@example.com", password_hash=hash_password("synthetic-password-user"), role="user")
        db.add(user)
        db.commit()
        user_id = user.id

    expiration = datetime.now(timezone.utc) + timedelta(minutes=5)
    payloads = [
        {"sub": str(user_id), "exp": expiration},
        {"sub": str(user_id), "exp": expiration, "ver": "0"},
        {"sub": str(user_id), "exp": expiration, "ver": -1},
        {"sub": str(user_id), "exp": expiration, "ver": True},
    ]
    signing_key = get_settings().signing_key()
    for payload in payloads:
        token = jwt.encode(payload, signing_key, algorithm="HS256")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_password_change_cannot_overwrite_a_newer_admin_reset(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="race-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        target = User(email="race-target@example.com", password_hash=hash_password("synthetic-password-old"), role="user")
        db.add_all([admin, target])
        db.commit()
        admin_headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
        target_id = target.id

    reset_url = f"/api/v1/users/{target_id}/password-reset"
    first_reset = client.post(reset_url, headers=admin_headers, json={"temporary_password": "synthetic-temporary-one"})
    assert first_reset.status_code == 200
    first_temp_login = client.post(
        "/api/v1/auth/login",
        json={"email": "race-target@example.com", "password": "synthetic-temporary-one"},
    )
    assert first_temp_login.status_code == 200
    stale_headers = {"Authorization": f"Bearer {first_temp_login.json()['access_token']}"}

    second_reset = client.post(reset_url, headers=admin_headers, json={"temporary_password": "synthetic-temporary-two"})
    assert second_reset.status_code == 200
    stale_change = client.post(
        "/api/v1/auth/change-password",
        headers=stale_headers,
        json={"current_password": "synthetic-temporary-one", "new_password": "synthetic-new-password"},
    )
    assert stale_change.status_code == 401

    with test_session() as db:
        target = db.get(User, target_id)
        assert target is not None
        assert target.must_change_password is True
        assert target.token_version == 2
        assert verify_password("synthetic-temporary-two", target.password_hash)
        assert not verify_password("synthetic-new-password", target.password_hash)


def test_password_change_reloads_locked_user_if_reset_occurs_after_auth(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        admin = User(email="interleave-admin@example.com", password_hash=hash_password("synthetic-password-admin"), role="admin")
        target = User(email="interleave-target@example.com", password_hash=hash_password("synthetic-password-old"), role="user")
        db.add_all([admin, target])
        db.commit()
        admin_id, target_id = admin.id, target.id
        stale_token = create_access_token(target.id, target.token_version)

    def reset_after_token_validation(request: Request, db=Depends(get_db)):
        target = db.get(User, target_id)
        admin = db.get(User, admin_id)
        assert target is not None and admin is not None
        # Simulate a reset committing after this request authenticated the old version,
        # but before the password-change handler obtains its row lock.
        request.state.auth_token_version = target.token_version
        user_endpoints.reset_user_password(
            target_id,
            UserPasswordReset(temporary_password="synthetic-racing-reset-password"),
            db,
            admin,
        )
        return target

    app.dependency_overrides[get_authenticated_user] = reset_after_token_validation
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {stale_token}"},
        json={"current_password": "synthetic-password-old", "new_password": "synthetic-racing-new-password"},
    )
    assert response.status_code == 401

    with test_session() as db:
        target = db.get(User, target_id)
        assert target is not None
        assert target.must_change_password is True
        assert target.token_version == 1
        assert verify_password("synthetic-racing-reset-password", target.password_hash)
        assert not verify_password("synthetic-racing-new-password", target.password_hash)


def test_notifications_are_limited_to_authenticated_user(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        first_user = User(email="notification-first@example.com", password_hash=hash_password("synthetic-password-first"), role="user")
        second_user = User(email="notification-second@example.com", password_hash=hash_password("synthetic-password-second"), role="user")
        db.add_all([first_user, second_user])
        db.flush()
        db.add_all(
            [
                Notification(user_id=first_user.id, message="Synthetic first-user notice", kind="system"),
                Notification(user_id=second_user.id, message="Synthetic second-user notice", kind="system"),
            ]
        )
        db.commit()
        first_token, second_token = create_access_token(first_user.id), create_access_token(second_user.id)

    first_response = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {first_token}"})
    second_response = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {second_token}"})

    assert first_response.status_code == 200
    assert [item["message"] for item in first_response.json()] == ["Synthetic first-user notice"]
    assert second_response.status_code == 200
    assert [item["message"] for item in second_response.json()] == ["Synthetic second-user notice"]
    assert client.get("/api/v1/notifications").status_code == 401


def test_authentication_and_patient_tenant_isolation(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        image_endpoints,
        "get_settings",
        lambda: Settings(upload_directory=tmp_path, max_upload_size_bytes=1024),
    )
    try:
        with test_session() as db:
            owner = User(email="owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="other@example.com", password_hash=hash_password("test-password-long"), role="user")
            admin = User(email="admin@example.com", password_hash=hash_password("test-password-long"), role="admin")
            db.add_all([owner, other, admin])
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="synthetic-test-record")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="synthetic-test-case")
            db.add(case)
            db.commit()
            patient_id, case_id = patient.id, case.id
            owner_token = create_access_token(owner.id)
            other_token = create_access_token(other.id)
            admin_token = create_access_token(admin.id)

        client = TestClient(app)
        assert client.get("/api/v1/patients").status_code == 401
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "test-password-long"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["token_type"] == "bearer"
        login_token = login_response.json()["access_token"]
        me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"})
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "owner@example.com"
        assert me_response.json()["role"] == "user"
        assert client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "incorrect-password"},
        ).status_code == 401
        assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {owner_token}"}).status_code == 403
        assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
        assert client.get(f"/api/v1/patients/{patient_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        upload = client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("artery.png", png_bytes(), "application/octet-stream")},
        )
        assert upload.status_code == 201, upload.text
        image_id = upload.json()["id"]
        assert client.get(f"/api/v1/images/{image_id}/content", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
        assert client.get(f"/api/v1/images/{image_id}/content", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("fake.png", b"not an image", "image/png")},
        ).status_code == 415
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("wrong.jpg", png_bytes(), "image/jpeg")},
        ).status_code == 415
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("large.png", b"x" * 1025, "image/png")},
        ).status_code == 413
        assert client.post(f"/api/v1/cases/{case_id}/analysis-runs", headers=owner_headers).status_code == 422
        assert client.get(f"/api/v1/analysis-runs/{uuid4()}", headers=owner_headers).status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_authenticated_user_can_update_only_own_profile_name(isolated_api_client):
    client, test_session = isolated_api_client
    with test_session() as db:
        owner = User(email="profile-owner@example.com", password_hash=hash_password("synthetic-owner-password"), role="user")
        other = User(email="profile-other@example.com", password_hash=hash_password("synthetic-other-password"), role="user")
        db.add_all([owner, other])
        db.commit()
        owner_id, other_id = owner.id, other.id
        owner_token = create_access_token(owner.id)
        other_token = create_access_token(other.id)

    endpoint = "/api/v1/auth/me/profile"
    assert client.patch(endpoint, json={"full_name": "Updated Name"}).status_code == 401
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    response = client.patch(endpoint, headers=owner_headers, json={"full_name": "  Lakshya  "})
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Lakshya"
    assert response.json()["role"] == "user"
    assert "password_hash" not in response.json()
    assert client.patch(endpoint, headers=owner_headers, json={"full_name": "Name", "role": "admin"}).status_code == 422
    assert client.patch(endpoint, headers={"Authorization": f"Bearer {other_token}"}, json={"full_name": "Other Name"}).status_code == 200
    assert client.patch(f"/api/v1/users/{owner_id}/profile", headers={"Authorization": f"Bearer {other_token}"}, json={"full_name": "Impersonated"}).status_code == 404
    with test_session() as db:
        assert db.get(User, owner_id).full_name == "Lakshya"
        assert db.get(User, owner_id).role == "user"
        assert db.get(User, other_id).full_name == "Other Name"
        assert db.get(User, other_id).role == "user"


def test_profile_email_change_requires_expiring_single_use_confirmation(isolated_api_client, monkeypatch, caplog):
    client, test_session = isolated_api_client
    settings = Settings(
        secret_key="local-test-signing-key-not-for-production-123456",
        smtp_host="smtp.example.test",
        smtp_from_email="no-reply@example.com",
        smtp_starttls=True,
        smtp_use_ssl=False,
        email_verification_ttl_minutes=30,
        login_rate_limit_attempts=20,
    )
    monkeypatch.setattr(auth_endpoints, "get_settings", lambda: settings)
    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_endpoints,
        "send_email_change_verification",
        lambda _settings, recipient, token: delivered.append((recipient, token)),
    )
    with test_session() as db:
        owner = User(
            email="verify-owner@example.com",
            password_hash=hash_password("synthetic-owner-password"),
            role="user",
        )
        db.add(owner)
        db.commit()
        owner_id = owner.id
        original_token = create_access_token(owner.id, owner.token_version)

    response = client.patch(
        "/api/v1/auth/me/profile",
        headers={"Authorization": f"Bearer {original_token}"},
        json={"email": "  New.Address@example.com "},
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "verify-owner@example.com"
    assert response.json()["email_verification_sent"] is True
    assert len(delivered) == 1
    assert delivered[0][0] == "new.address@example.com"
    verification_token = delivered[0][1]
    assert verification_token not in response.text
    with test_session() as db:
        owner = db.get(User, owner_id)
        verification = db.query(EmailChangeVerification).filter_by(user_id=owner_id).one()
        assert owner.email == "verify-owner@example.com"
        assert verification.pending_email == "new.address@example.com"
        assert verification.token_hash == hashlib.sha256(verification_token.encode()).hexdigest()
        assert verification.token_hash != verification_token

    verified = client.post("/api/v1/auth/verify-email-change", json={"token": verification_token})
    assert verified.status_code == 200, verified.text
    assert "token" not in verified.text.lower()
    with test_session() as db:
        owner = db.get(User, owner_id)
        assert owner.email == "new.address@example.com"
        assert owner.token_version == 1
        assert db.query(EmailChangeVerification).filter_by(user_id=owner_id).count() == 0

    assert client.post("/api/v1/auth/verify-email-change", json={"token": verification_token}).status_code == 400
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {original_token}"}).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "verify-owner@example.com", "password": "synthetic-owner-password"},
    ).status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "new.address@example.com", "password": "synthetic-owner-password"},
    )
    assert new_login.status_code == 200
    assert verification_token not in caplog.text


def test_profile_email_change_requires_delivery_and_rejects_invalid_or_duplicate_email(isolated_api_client, monkeypatch):
    client, test_session = isolated_api_client
    with test_session() as db:
        owner = User(email="email-owner@example.com", password_hash=hash_password("synthetic-owner-password"), role="user")
        existing = User(email="email-existing@example.com", password_hash=hash_password("synthetic-existing-password"), role="user")
        db.add_all([owner, existing])
        db.commit()
        owner_id, owner_token = owner.id, create_access_token(owner.id, owner.token_version)
    headers = {"Authorization": f"Bearer {owner_token}"}

    no_delivery = Settings(secret_key="local-test-signing-key-not-for-production-123456")
    monkeypatch.setattr(auth_endpoints, "get_settings", lambda: no_delivery)
    assert client.patch("/api/v1/auth/me/profile", headers=headers, json={"email": "new@example.com"}).status_code == 503
    assert client.patch("/api/v1/auth/me/profile", headers=headers, json={"email": "invalid-address"}).status_code == 422

    configured = Settings(
        secret_key="local-test-signing-key-not-for-production-123456",
        smtp_host="smtp.example.test",
        smtp_from_email="no-reply@example.com",
    )
    monkeypatch.setattr(auth_endpoints, "get_settings", lambda: configured)
    duplicate = client.patch("/api/v1/auth/me/profile", headers=headers, json={"email": "EMAIL-EXISTING@example.com"})
    assert duplicate.status_code == 409
    with test_session() as db:
        assert db.get(User, owner_id).email == "email-owner@example.com"
        assert db.query(EmailChangeVerification).filter_by(user_id=owner_id).count() == 0


def test_expired_email_change_token_is_rejected_and_removed(isolated_api_client):
    client, test_session = isolated_api_client
    token = "synthetic-expired-verification-token-0123456789"
    with test_session() as db:
        owner = User(email="expired-owner@example.com", password_hash=hash_password("synthetic-owner-password"), role="user")
        db.add(owner)
        db.flush()
        db.add(EmailChangeVerification(
            user_id=owner.id,
            pending_email="expired-new@example.com",
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        db.commit()
        owner_id = owner.id

    response = client.post("/api/v1/auth/verify-email-change", json={"token": token})
    assert response.status_code == 400
    with test_session() as db:
        assert db.get(User, owner_id).email == "expired-owner@example.com"
        assert db.query(EmailChangeVerification).filter_by(user_id=owner_id).count() == 0


def test_login_rate_limit_uses_persisted_hashed_buckets(isolated_api_client, monkeypatch):
    client, test_session = isolated_api_client
    settings = Settings(
        secret_key="local-test-signing-key-not-for-production-123456",
        login_rate_limit_attempts=2,
        login_rate_limit_window_seconds=900,
    )
    monkeypatch.setattr(auth_endpoints, "get_settings", lambda: settings)

    attempts = [
        client.post("/api/v1/auth/login", json={"email": "rate@example.com", "password": "wrong-password"})
        for _ in range(3)
    ]
    assert [response.status_code for response in attempts] == [401, 401, 429]
    assert int(attempts[-1].headers["retry-after"]) > 0
    with test_session() as db:
        buckets = db.query(LoginRateLimitBucket).all()
        assert len(buckets) == 2
        assert all("rate@example.com" not in bucket.bucket_key for bucket in buckets)


def test_case_crud_validation_and_tenant_isolation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with test_session() as db:
            admin = User(email="case-admin@example.com", full_name="Lakshya", password_hash=hash_password("test-password-long"), role="admin")
            owner = User(email="case-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="case-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            owner.full_name = "Case Owner"
            other.full_name = "Other Owner"
            db.add_all([admin, owner, other])
            db.flush()
            owner_patient = Patient(owner_id=owner.id, patient_ref="case-owner-patient")
            other_patient = Patient(owner_id=other.id, patient_ref="case-other-patient")
            admin_patient = Patient(owner_id=admin.id, patient_ref="case-admin-patient")
            db.add_all([owner_patient, other_patient, admin_patient])
            db.flush()
            admin_case = Case(owner_id=admin.id, patient_id=admin_patient.id, case_ref="case-admin-record", modality="CTA")
            other_case = Case(owner_id=other.id, patient_id=other_patient.id, case_ref="case-other-record", modality="CTA")
            db.add_all([admin_case, other_case])
            db.commit()
            owner_id, other_id, admin_id = owner.id, other.id, admin.id
            owner_patient_id, other_patient_id = owner_patient.id, other_patient.id

        client = TestClient(app)
        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
        admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

        assert client.get("/api/v1/cases").status_code == 401
        assert client.get("/api/v1/cases", headers=owner_headers).json() == []
        assert client.post(
            "/api/v1/cases",
            headers=owner_headers,
            json={"patient_id": str(owner_patient_id), "case_ref": "  ", "modality": "CTA"},
        ).status_code == 422
        assert client.post(
            "/api/v1/cases",
            headers=owner_headers,
            json={"patient_id": str(other_patient_id), "case_ref": "cross-owner", "modality": "CTA"},
        ).status_code == 404

        created = client.post(
            "/api/v1/cases",
            headers=owner_headers,
            json={"patient_id": str(owner_patient_id), "case_ref": "case-001", "modality": "CTA"},
        )
        assert created.status_code == 201, created.text
        created_case = created.json()
        case_id = created_case["id"]
        assert created_case["patient_id"] == str(owner_patient_id)
        assert created_case["case_ref"] == "case-001"
        assert created_case["modality"] == "CTA"
        assert created_case["owner_name"] == "Case Owner"

        listed = client.get("/api/v1/cases", headers=owner_headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [case_id]
        assert [item["id"] for item in client.get("/api/v1/cases", headers=other_headers).json()] == [str(other_case.id)]
        admin_listed = client.get("/api/v1/cases", headers=admin_headers)
        assert admin_listed.status_code == 200
        assert {item["id"] for item in admin_listed.json()} == {case_id, str(admin_case.id), str(other_case.id)}
        assert next(item for item in admin_listed.json() if item["id"] == str(admin_case.id))["owner_name"] == "Lakshya"
        assert next(item for item in admin_listed.json() if item["id"] == str(other_case.id))["owner_name"] == "Other Owner"
        assert client.get(f"/api/v1/cases/{case_id}", headers=admin_headers).status_code == 200
        assert client.get(f"/api/v1/cases/{case_id}", headers=owner_headers).json()["id"] == case_id
        assert client.get(f"/api/v1/cases/{case_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/v1/cases/{other_case.id}", headers=owner_headers).status_code == 404
        assert client.patch(
            f"/api/v1/cases/{case_id}",
            headers=other_headers,
            json={"case_ref": "stolen-update"},
        ).status_code == 404
        assert client.patch(
            f"/api/v1/cases/{case_id}",
            headers=owner_headers,
            json={"case_ref": "  "},
        ).status_code == 422
        assert client.patch(
            f"/api/v1/cases/{case_id}",
            headers=owner_headers,
            json={"case_ref": "case-001-updated", "modality": "Angiography"},
        ).status_code == 200
        persisted = client.get(f"/api/v1/cases/{case_id}", headers=owner_headers)
        assert persisted.status_code == 200
        assert persisted.json()["case_ref"] == "case-001-updated"
        assert persisted.json()["modality"] == "Angiography"
        cleared_modality = client.patch(
            f"/api/v1/cases/{case_id}",
            headers=owner_headers,
            json={"modality": None},
        )
        assert cleared_modality.status_code == 200
        assert cleared_modality.json()["modality"] is None
        assert client.post(
            "/api/v1/cases",
            headers=owner_headers,
            json={"patient_id": str(owner_patient_id), "case_ref": "case-001-updated", "modality": None},
        ).status_code == 409
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_patient_crud_validation_persistence_and_tenant_isolation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with test_session() as db:
            admin = User(email="patient-admin@example.com", full_name="Lakshya", password_hash=hash_password("test-password-long"), role="admin")
            owner = User(email="patient-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="patient-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            owner.full_name = "Patient Owner"
            other.full_name = "Other Patient Owner"
            db.add_all([admin, owner, other])
            db.flush()
            existing_patient = Patient(owner_id=owner.id, patient_ref="existing-patient")
            other_patient = Patient(owner_id=other.id, patient_ref="other-patient")
            admin_patient = Patient(owner_id=admin.id, patient_ref="admin-patient")
            db.add_all([existing_patient, other_patient, admin_patient])
            db.commit()
            owner_id, other_id, admin_id = owner.id, other.id, admin.id
            existing_patient_id, other_patient_id, admin_patient_id = existing_patient.id, other_patient.id, admin_patient.id

        client = TestClient(app)
        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
        admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

        assert client.get("/api/v1/patients").status_code == 401
        listed = client.get("/api/v1/patients", headers=owner_headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [str(existing_patient_id)]
        assert listed.json()[0]["owner_name"] == "Patient Owner"
        all_patients = client.get("/api/v1/patients", headers=admin_headers)
        assert all_patients.status_code == 200
        assert {item["id"] for item in all_patients.json()} == {str(existing_patient_id), str(other_patient_id), str(admin_patient_id)}
        assert next(item for item in all_patients.json() if item["id"] == str(admin_patient_id))["owner_name"] == "Lakshya"
        assert client.get(f"/api/v1/patients/{existing_patient_id}", headers=owner_headers).status_code == 200
        assert client.get(f"/api/v1/patients/{existing_patient_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/v1/patients/{other_patient_id}", headers=owner_headers).status_code == 404
        assert client.get(f"/api/v1/patients/{other_patient_id}", headers=admin_headers).status_code == 200
        assert client.patch(
            f"/api/v1/patients/{existing_patient_id}",
            headers=other_headers,
            json={"patient_ref": "unauthorized-change"},
        ).status_code == 404
        assert client.post("/api/v1/patients", headers=owner_headers, json={"patient_ref": "  "}).status_code == 422
        assert client.post(
            "/api/v1/patients",
            headers=owner_headers,
            json={"patient_ref": "invalid-owner", "owner_id": str(other_id)},
        ).status_code == 403

        created = client.post("/api/v1/patients", headers=owner_headers, json={"patient_ref": "new-patient"})
        assert created.status_code == 201, created.text
        patient_id = created.json()["id"]
        assert created.json()["owner_id"] == str(owner_id)
        assert created.json()["owner_name"] == "Patient Owner"
        assert client.get(f"/api/v1/patients/{patient_id}", headers=owner_headers).json()["patient_ref"] == "new-patient"

        assert client.patch(
            f"/api/v1/patients/{patient_id}",
            headers=owner_headers,
            json={"patient_ref": "  "},
        ).status_code == 422
        updated = client.patch(
            f"/api/v1/patients/{patient_id}",
            headers=owner_headers,
            json={"patient_ref": "updated-patient"},
        )
        assert updated.status_code == 200
        assert updated.json()["patient_ref"] == "updated-patient"
        persisted = client.get(f"/api/v1/patients/{patient_id}", headers=owner_headers)
        assert persisted.status_code == 200
        assert persisted.json()["patient_ref"] == "updated-patient"
        assert client.post(
            "/api/v1/patients",
            headers=owner_headers,
            json={"patient_ref": "updated-patient"},
        ).status_code == 409
        other_list = client.get("/api/v1/patients", headers=other_headers)
        assert other_list.status_code == 200
        assert [item["id"] for item in other_list.json()] == [str(other_patient_id)]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_image_upload_listing_persistence_and_case_ownership(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        image_endpoints,
        "get_settings",
        lambda: Settings(upload_directory=tmp_path, max_upload_size_bytes=1024),
    )
    monkeypatch.setattr(
        preprocessing_endpoints,
        "get_settings",
        lambda: Settings(upload_directory=tmp_path, max_upload_size_bytes=1024),
    )
    try:
        with test_session() as db:
            owner = User(email="image-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="image-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add_all([owner, other])
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="image-patient")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="image-case")
            db.add(case)
            db.commit()
            owner_id, other_id, case_id = owner.id, other.id, case.id

        client = TestClient(app)
        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
        original = png_bytes()

        assert client.get(f"/api/v1/cases/{case_id}/images").status_code == 401
        uploaded = client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("study.png", original, "application/octet-stream")},
        )
        assert uploaded.status_code == 201, uploaded.text
        image = uploaded.json()
        assert image["case_id"] == str(case_id)
        assert image["original_filename"] == "study.png"
        assert image["media_type"] == "image/png"
        assert image["size_bytes"] == len(original)
        assert len(list(tmp_path.iterdir())) == 1

        listed = client.get(f"/api/v1/cases/{case_id}/images", headers=owner_headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [image["id"]]
        initial_status = client.get(f"/api/v1/cases/{case_id}/preprocessing", headers=owner_headers)
        assert initial_status.status_code == 200
        assert initial_status.json()[0]["status"] == "not_started"
        assert initial_status.json()[0]["result"] is None
        assert client.get(f"/api/v1/cases/{case_id}/preprocessing").status_code == 401
        assert client.get(f"/api/v1/cases/{case_id}/preprocessing", headers=other_headers).status_code == 404
        persisted = client.get(f"/api/v1/cases/{case_id}/images", headers=owner_headers)
        assert persisted.status_code == 200
        assert persisted.json()[0]["id"] == image["id"]
        content = client.get(f"/api/v1/images/{image['id']}/content", headers=owner_headers)
        assert content.status_code == 200
        assert content.headers["cache-control"] == "private, no-store"
        assert content.content == original

        prepared = client.post(f"/api/v1/images/{image['id']}/preprocess", headers=owner_headers)
        assert prepared.status_code == 200, prepared.text
        response = prepared.json()
        metadata = response["result"]
        assert response["status"] == "completed"
        assert response["attempt_count"] == 1
        assert metadata["output_shape"] == [1, 256, 256]
        assert metadata["data_type"] == "float32"
        assert metadata["output_persisted"] is False
        assert "No segmentation" in response["message"]
        reloaded_status = client.get(f"/api/v1/cases/{case_id}/preprocessing", headers=owner_headers)
        assert reloaded_status.status_code == 200
        assert reloaded_status.json()[0]["status"] == "completed"
        assert reloaded_status.json()[0]["result"] == metadata
        assert "pixels" not in reloaded_status.json()[0]["result"]
        with test_session() as db:
            saved_preprocessing = db.get(ImagePreprocessing, UUID(image["id"]))
            assert saved_preprocessing is not None
            assert saved_preprocessing.preprocessed_by_id == owner_id
            assert "pixels" not in saved_preprocessing.result_metadata

        stored_path = next(tmp_path.iterdir())
        stored_path.write_bytes(b"corrupted image")
        failed = client.post(f"/api/v1/images/{image['id']}/preprocess", headers=owner_headers)
        assert failed.status_code == 415
        failed_status = client.get(f"/api/v1/cases/{case_id}/preprocessing", headers=owner_headers).json()[0]
        assert failed_status["status"] == "failed"
        assert failed_status["attempt_count"] == 2
        assert failed_status["result"] is None
        stored_path.write_bytes(original)
        retried = client.post(f"/api/v1/images/{image['id']}/preprocess", headers=owner_headers)
        assert retried.status_code == 200
        assert retried.json()["status"] == "completed"
        assert retried.json()["attempt_count"] == 3
        assert client.post(f"/api/v1/images/{image['id']}/preprocess", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/images/{image['id']}/preprocess").status_code == 401
        assert content.content == original

        assert client.get(f"/api/v1/cases/{case_id}/images", headers=other_headers).status_code == 404
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=other_headers,
            files={"file": ("other.png", original, "image/png")},
        ).status_code == 404
        assert client.get(f"/api/v1/images/{image['id']}/content", headers=other_headers).status_code == 404
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("bad.gif", original, "image/gif")},
        ).status_code == 415
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("bad.png", b"not an image", "image/png")},
        ).status_code == 415
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("wrong.jpg", original, "image/jpeg")},
        ).status_code == 415
        assert client.post(
            f"/api/v1/cases/{case_id}/images",
            headers=owner_headers,
            files={"file": ("large.png", b"x" * 1025, "image/png")},
        ).status_code == 413
        assert client.get(f"/api/v1/images/{image['id']}/content").status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_admin_deletes_regular_user_and_all_dependent_records(isolated_api_client, tmp_path, monkeypatch):
    client, test_session = isolated_api_client
    upload_directory = tmp_path / "uploads"
    analysis_directory = tmp_path / "analysis"
    settings = Settings(upload_directory=upload_directory, analysis_output_directory=analysis_directory)
    monkeypatch.setattr(user_endpoints, "get_settings", lambda: settings)
    with test_session() as db:
        admin = User(email="delete-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        target = User(email="delete-target@example.com", password_hash=hash_password("synthetic-target-password"), role="user")
        other = User(email="delete-other@example.com", password_hash=hash_password("synthetic-other-password"), role="user")
        db.add_all([admin, target, other])
        db.flush()
        admin_patient = Patient(owner_id=admin.id, patient_ref="admin-unrelated-patient")
        target_patient = Patient(owner_id=target.id, patient_ref="target-patient")
        other_patient = Patient(owner_id=other.id, patient_ref="other-patient")
        db.add_all([admin_patient, target_patient, other_patient])
        db.flush()
        admin_case = Case(owner_id=admin.id, patient_id=admin_patient.id, case_ref="admin-unrelated-case")
        target_case = Case(owner_id=target.id, patient_id=target_patient.id, case_ref="target-case")
        other_case = Case(owner_id=other.id, patient_id=other_patient.id, case_ref="other-case")
        db.add_all([admin_case, target_case, other_case])
        db.flush()
        admin_image = MedicalImage(
            case_id=admin_case.id, uploaded_by_id=admin.id, storage_key="admin-unrelated-image.png",
            original_filename="admin-unrelated.png", media_type="image/png", size_bytes=1, sha256="e" * 64,
        )
        target_image = MedicalImage(
            case_id=target_case.id, uploaded_by_id=target.id, storage_key="target-image.png",
            original_filename="target.png", media_type="image/png", size_bytes=1, sha256="a" * 64,
        )
        other_image = MedicalImage(
            case_id=other_case.id, uploaded_by_id=other.id, storage_key="other-image.png",
            original_filename="other.png", media_type="image/png", size_bytes=1, sha256="b" * 64,
        )
        db.add_all([admin_image, target_image, other_image])
        db.flush()
        admin_unrelated_run = AnalysisRun(case_id=admin_case.id, image_id=admin_image.id, requested_by_id=admin.id, status="completed", result_metadata={"candidate_count": 4})
        target_run = AnalysisRun(case_id=target_case.id, image_id=target_image.id, requested_by_id=target.id, status="completed", result_metadata={"candidate_count": 1})
        admin_run_on_target_image = AnalysisRun(
            case_id=target_case.id,
            image_id=target_image.id,
            requested_by_id=admin.id,
            status="completed",
            result_metadata={"candidate_count": 3},
        )
        other_run = AnalysisRun(case_id=other_case.id, image_id=other_image.id, requested_by_id=other.id, status="completed", result_metadata={"candidate_count": 2})
        db.add_all([
            ImagePreprocessing(image_id=target_image.id, preprocessed_by_id=admin.id, status="completed", attempt_count=1, result_metadata={"output_shape": [1, 256, 256]}),
            ImagePreprocessing(image_id=other_image.id, preprocessed_by_id=other.id, status="completed", attempt_count=1, result_metadata={"output_shape": [1, 256, 256]}),
            admin_unrelated_run,
            target_run,
            admin_run_on_target_image,
            other_run,
            Notification(user_id=target.id, message="Target notification"),
            Notification(user_id=other.id, message="Other notification"),
        ])
        db.commit()
        admin_id, target_id, other_id = admin.id, target.id, other.id
        target_patient_id, other_patient_id = target_patient.id, other_patient.id
        target_case_id, other_case_id = target_case.id, other_case.id
        target_image_id, other_image_id = target_image.id, other_image.id
        admin_patient_id, admin_case_id, admin_image_id = admin_patient.id, admin_case.id, admin_image.id
        admin_unrelated_run_id = admin_unrelated_run.id
        target_run_id, admin_run_id, other_run_id = target_run.id, admin_run_on_target_image.id, other_run.id

    upload_directory.mkdir(parents=True)
    (upload_directory / "target-image.png").write_bytes(b"synthetic target file")
    (upload_directory / "other-image.png").write_bytes(b"synthetic other file")
    (upload_directory / "admin-unrelated-image.png").write_bytes(b"synthetic unrelated admin file")
    run_dir = analysis_directory / target_run_id.hex
    run_dir.mkdir(parents=True)
    (run_dir / "candidate_overlay.png").write_bytes(b"synthetic artifact")
    other_run_dir = analysis_directory / other_run_id.hex
    other_run_dir.mkdir(parents=True)
    (other_run_dir / "candidate_overlay.png").write_bytes(b"other artifact")
    admin_run_dir = analysis_directory / admin_run_id.hex
    admin_run_dir.mkdir(parents=True)
    (admin_run_dir / "candidate_overlay.png").write_bytes(b"dependent admin artifact")
    admin_unrelated_run_dir = analysis_directory / admin_unrelated_run_id.hex
    admin_unrelated_run_dir.mkdir(parents=True)
    (admin_unrelated_run_dir / "candidate_overlay.png").write_bytes(b"unrelated admin artifact")
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
    target_headers = {"Authorization": f"Bearer {create_access_token(target_id)}"}

    deleted = client.delete(f"/api/v1/users/{target_id}", headers=admin_headers)

    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["cleanup_status"] == "complete"
    assert client.delete(f"/api/v1/users/{target_id}", headers=admin_headers).status_code == 404
    assert not (upload_directory / "target-image.png").exists()
    assert (upload_directory / "other-image.png").exists()
    assert not run_dir.exists()
    assert not admin_run_dir.exists()
    assert other_run_dir.exists()
    assert (upload_directory / "admin-unrelated-image.png").exists()
    assert admin_unrelated_run_dir.exists()
    assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "delete-target@example.com", "password": "synthetic-target-password"}).status_code == 401
    with test_session() as db:
        assert db.get(User, admin_id) is not None
        assert db.get(Patient, admin_patient_id) is not None
        assert db.get(Case, admin_case_id) is not None
        assert db.get(MedicalImage, admin_image_id) is not None
        assert db.get(AnalysisRun, admin_unrelated_run_id) is not None
        assert db.get(User, target_id) is None
        assert db.get(Patient, target_patient_id) is None
        assert db.get(Case, target_case_id) is None
        assert db.get(MedicalImage, target_image_id) is None
        assert db.get(AnalysisRun, target_run_id) is None
        assert db.get(AnalysisRun, admin_run_id) is None
        assert db.scalar(select(ImagePreprocessing).where(ImagePreprocessing.image_id == target_image_id)) is None
        assert db.get(User, other_id) is not None
        assert db.get(Patient, other_patient_id) is not None
        assert db.get(Case, other_case_id) is not None
        assert db.get(MedicalImage, other_image_id) is not None
        assert db.get(AnalysisRun, other_run_id) is not None
        assert db.scalar(select(Notification).where(Notification.user_id == other_id)) is not None


def test_user_deletion_rejects_unauthorized_admin_and_self_targets(isolated_api_client, monkeypatch, tmp_path):
    client, test_session = isolated_api_client
    monkeypatch.setattr(
        user_endpoints, "get_settings",
        lambda: Settings(upload_directory=tmp_path / "uploads", analysis_output_directory=tmp_path / "analysis"),
    )
    with test_session() as db:
        admin = User(email="delete-guard-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        regular = User(email="delete-guard-user@example.com", password_hash=hash_password("synthetic-user-password"), role="user")
        db.add_all([admin, regular])
        db.commit()
        admin_id, regular_id = admin.id, regular.id
        admin_token, regular_token = create_access_token(admin.id), create_access_token(regular.id)

    assert client.delete(f"/api/v1/users/{regular_id}").status_code == 401
    assert client.delete(f"/api/v1/users/{regular_id}", headers={"Authorization": f"Bearer {regular_token}"}).status_code == 403
    assert client.get("/api/v1/users/deletion-cleanups").status_code == 401
    assert client.get("/api/v1/users/deletion-cleanups", headers={"Authorization": f"Bearer {regular_token}"}).status_code == 403
    assert client.delete(f"/api/v1/users/{admin_id}", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 409
    assert client.delete(f"/api/v1/users/{uuid4()}", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 404
    with test_session() as db:
        assert db.get(User, admin_id) is not None
        assert db.get(User, regular_id) is not None


def test_admin_deletes_regular_user_without_associated_records(isolated_api_client, monkeypatch, tmp_path):
    client, test_session = isolated_api_client
    monkeypatch.setattr(
        user_endpoints, "get_settings",
        lambda: Settings(upload_directory=tmp_path / "uploads", analysis_output_directory=tmp_path / "analysis"),
    )
    with test_session() as db:
        admin = User(email="delete-empty-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        target = User(email="delete-empty-target@example.com", password_hash=hash_password("synthetic-target-password"), role="user")
        db.add_all([admin, target])
        db.commit()
        admin_id, target_id = admin.id, target.id
    response = client.delete(
        f"/api/v1/users/{target_id}",
        headers={"Authorization": f"Bearer {create_access_token(admin_id)}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cleanup_status"] == "complete"
    with test_session() as db:
        assert db.get(User, target_id) is None


def test_user_deletion_removes_case_dependent_on_target_patient_but_preserves_other_user(isolated_api_client, monkeypatch, tmp_path):
    client, test_session = isolated_api_client
    upload_directory, analysis_directory = tmp_path / "uploads", tmp_path / "analysis"
    monkeypatch.setattr(user_endpoints, "get_settings", lambda: Settings(upload_directory=upload_directory, analysis_output_directory=analysis_directory))
    with test_session() as db:
        admin = User(email="delete-shared-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        target = User(email="delete-shared-target@example.com", password_hash=hash_password("synthetic-target-password"), role="user")
        other = User(email="delete-shared-other@example.com", password_hash=hash_password("synthetic-other-password"), role="user")
        db.add_all([admin, target, other])
        db.flush()
        patient = Patient(owner_id=target.id, patient_ref="shared-target-patient")
        other_patient = Patient(owner_id=other.id, patient_ref="unrelated-other-patient")
        db.add_all([patient, other_patient])
        db.flush()
        foreign_case = Case(owner_id=other.id, patient_id=patient.id, case_ref="foreign-case")
        unrelated_case = Case(owner_id=other.id, patient_id=other_patient.id, case_ref="unrelated-case")
        db.add_all([foreign_case, unrelated_case])
        db.commit()
        admin_id, target_id, patient_id, case_id = admin.id, target.id, patient.id, foreign_case.id
        other_id, other_patient_id, unrelated_case_id = other.id, other_patient.id, unrelated_case.id
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
    response = client.delete(f"/api/v1/users/{target_id}", headers=admin_headers)
    assert response.status_code == 200, response.text
    with test_session() as db:
        assert db.get(User, target_id) is None
        assert db.get(Patient, patient_id) is None
        assert db.get(Case, case_id) is None
        assert db.get(User, other_id) is not None
        assert db.get(Patient, other_patient_id) is not None
        assert db.get(Case, unrelated_case_id) is not None


def test_user_deletion_transaction_failure_rolls_back_database(isolated_api_client, monkeypatch, tmp_path):
    client, test_session = isolated_api_client
    monkeypatch.setattr(user_endpoints, "get_settings", lambda: Settings(upload_directory=tmp_path / "uploads", analysis_output_directory=tmp_path / "analysis"))
    with test_session() as db:
        admin = User(email="delete-rollback-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        target = User(email="delete-rollback-target@example.com", password_hash=hash_password("synthetic-target-password"), role="user")
        db.add_all([admin, target])
        db.commit()
        admin_id, target_id = admin.id, target.id
    original_commit = Session.commit
    def failed_commit(_session):
        raise RuntimeError("synthetic database commit failure")
    monkeypatch.setattr(Session, "commit", failed_commit)
    response = client.delete(f"/api/v1/users/{target_id}", headers={"Authorization": f"Bearer {create_access_token(admin_id)}"})
    monkeypatch.setattr(Session, "commit", original_commit)
    assert response.status_code == 500
    with test_session() as db:
        assert db.get(User, target_id) is not None


def test_user_deletion_cleanup_failure_is_reported_and_retryable(isolated_api_client, monkeypatch, tmp_path):
    client, test_session = isolated_api_client
    upload_directory, analysis_directory = tmp_path / "uploads", tmp_path / "analysis"
    settings = Settings(upload_directory=upload_directory, analysis_output_directory=analysis_directory)
    monkeypatch.setattr(user_endpoints, "get_settings", lambda: settings)
    with test_session() as db:
        admin = User(email="delete-retry-admin@example.com", password_hash=hash_password("synthetic-admin-password"), role="admin")
        target = User(email="delete-retry-target@example.com", password_hash=hash_password("synthetic-target-password"), role="user")
        other = User(email="delete-retry-other@example.com", password_hash=hash_password("synthetic-other-password"), role="user")
        db.add_all([admin, target, other])
        db.flush()
        patient = Patient(owner_id=target.id, patient_ref="retry-patient")
        db.add(patient)
        db.flush()
        case = Case(owner_id=target.id, patient_id=patient.id, case_ref="retry-case")
        db.add(case)
        db.flush()
        image = MedicalImage(case_id=case.id, uploaded_by_id=target.id, storage_key="retry-image.png", original_filename="retry.png", media_type="image/png", size_bytes=1, sha256="c" * 64)
        db.add(image)
        db.flush()
        run = AnalysisRun(case_id=case.id, image_id=image.id, requested_by_id=target.id, status="completed", result_metadata={"candidate_count": 0})
        db.add(run)
        db.flush()
        other_patient = Patient(owner_id=other.id, patient_ref="retry-other-patient")
        db.add(other_patient)
        db.flush()
        other_case = Case(owner_id=other.id, patient_id=other_patient.id, case_ref="retry-other-case")
        db.add(other_case)
        db.commit()
        admin_id, target_id, run_id, other_id, other_case_id = admin.id, target.id, run.id, other.id, other_case.id
    upload_directory.mkdir(parents=True)
    file_path = upload_directory / "retry-image.png"
    file_path.write_bytes(b"synthetic upload")
    run_directory = analysis_directory / run_id.hex
    run_directory.mkdir(parents=True)
    (run_directory / "candidate_overlay.png").write_bytes(b"synthetic generated artifact")
    original_delete = user_deletion_service._delete_upload_file
    def fail_file_cleanup(_path):
        raise OSError("synthetic storage failure")
    monkeypatch.setattr(user_deletion_service, "_delete_upload_file", fail_file_cleanup)
    admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

    deleted = client.delete(f"/api/v1/users/{target_id}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    deletion = deleted.json()
    assert deletion["cleanup_status"] == "pending"
    assert deletion["cleanup_id"]
    assert file_path.exists()
    assert run_directory.exists()
    pending = client.get("/api/v1/users/deletion-cleanups", headers=admin_headers)
    assert pending.status_code == 200
    assert pending.json()[0]["storage_file_count"] == 1
    assert pending.json()[0]["analysis_run_count"] == 1

    # A newly surviving database reference must prevent the retry from
    # removing the same physical file until that reference is gone.
    with test_session() as db:
        db.add(MedicalImage(
            case_id=other_case_id,
            uploaded_by_id=other_id,
            storage_key="retry-image.png",
            original_filename="other-reference.png",
            media_type="image/png",
            size_bytes=1,
            sha256="d" * 64,
        ))
        db.commit()
    deferred = client.post(f"/api/v1/users/deletion-cleanups/{deletion['cleanup_id']}/retry", headers=admin_headers)
    assert deferred.status_code == 200
    assert deferred.json()["status"] == "pending"
    assert file_path.exists()

    with test_session() as db:
        surviving_image = db.scalar(select(MedicalImage).where(MedicalImage.storage_key == "retry-image.png"))
        db.delete(surviving_image)
        db.commit()

    monkeypatch.setattr(user_deletion_service, "_delete_upload_file", original_delete)
    retried = client.post(f"/api/v1/users/deletion-cleanups/{deletion['cleanup_id']}/retry", headers=admin_headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "complete"
    assert not file_path.exists()
    assert not run_directory.exists()
    assert client.get("/api/v1/users/deletion-cleanups", headers=admin_headers).json() == []
    with test_session() as db:
        assert db.get(User, admin_id) is not None
        assert db.get(User, other_id) is not None
        assert db.get(Case, other_case_id) is not None

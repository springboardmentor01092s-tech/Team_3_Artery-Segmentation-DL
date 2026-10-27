import io
import os
from uuid import UUID, uuid4

os.environ.setdefault("SECRET_KEY", "local-test-signing-key-not-for-production-123456")
os.environ.setdefault("POSTGRES_PASSWORD", "local-test-password")

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import images as image_endpoints, preprocessing as preprocessing_endpoints
from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.case import Case
from app.models.image_preprocessing import ImagePreprocessing
from app.models.patient import Patient
from app.models.user import User


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), color=(120, 120, 120)).save(stream, format="PNG")
    return stream.getvalue()


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
        assert client.post(f"/api/v1/cases/{case_id}/analysis-runs", headers=owner_headers).status_code == 503
        assert client.get(f"/api/v1/analysis-runs/{uuid4()}", headers=owner_headers).status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


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
            owner = User(email="case-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="case-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add_all([owner, other])
            db.flush()
            owner_patient = Patient(owner_id=owner.id, patient_ref="case-owner-patient")
            other_patient = Patient(owner_id=other.id, patient_ref="case-other-patient")
            db.add_all([owner_patient, other_patient])
            db.commit()
            owner_id, other_id = owner.id, other.id
            owner_patient_id, other_patient_id = owner_patient.id, other_patient.id

        client = TestClient(app)
        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}

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

        listed = client.get("/api/v1/cases", headers=owner_headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [case_id]
        assert client.get("/api/v1/cases", headers=other_headers).json() == []
        assert client.get(f"/api/v1/cases/{case_id}", headers=owner_headers).json()["id"] == case_id
        assert client.get(f"/api/v1/cases/{case_id}", headers=other_headers).status_code == 404
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
            owner = User(email="patient-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="patient-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add_all([owner, other])
            db.flush()
            existing_patient = Patient(owner_id=owner.id, patient_ref="existing-patient")
            other_patient = Patient(owner_id=other.id, patient_ref="other-patient")
            db.add_all([existing_patient, other_patient])
            db.commit()
            owner_id, other_id = owner.id, other.id
            existing_patient_id, other_patient_id = existing_patient.id, other_patient.id

        client = TestClient(app)
        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}

        assert client.get("/api/v1/patients").status_code == 401
        listed = client.get("/api/v1/patients", headers=owner_headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [str(existing_patient_id)]
        assert client.get(f"/api/v1/patients/{existing_patient_id}", headers=owner_headers).status_code == 200
        assert client.get(f"/api/v1/patients/{existing_patient_id}", headers=other_headers).status_code == 404
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

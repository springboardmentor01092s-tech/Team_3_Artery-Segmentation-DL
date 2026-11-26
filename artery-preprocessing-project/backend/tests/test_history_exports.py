import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.api import analysis as analysis_api
from app.core.permissions import UserRole
from app.models.analysis import StenosisAnalysis
from app.models.case import Case
from app.models.case_access import CaseAccess
from app.models.image import UploadedImage
from app.models.preprocessing import PreprocessingRun
from tests.conftest import auth_header, make_user


def _seed_history(db, owner, admin, *, analysis_count=2, shared_user_id=None, assigned_user_id=None,
                  analysis_prefix="history", case_identifier="HISTORY-CASE-1"):
    case = Case(
        case_identifier=case_identifier,
        patient_identifier="PSEUDO-1",
        imaging_modality="XCA",
        anatomical_region="coronary",
        owner_id=owner.id,
    )
    db.add(case)
    db.flush()
    image = UploadedImage(
        case_id=case.id,
        original_filename="angiogram.png",
        storage_filename=f"{analysis_prefix}-history-test-image.png",
        format="PNG",
        file_size=1234,
        width=512,
        height=512,
        uploaded_by_id=owner.id,
    )
    db.add(image)
    db.flush()
    db.add(PreprocessingRun(
        case_id=case.id,
        image_id=image.id,
        config_json=json.dumps({"resize": [512, 512], "notes": 'clip, "contrast"\nkeep spacing'}),
        input_format="PNG",
        original_width=512,
        original_height=512,
        processed_width=512,
        processed_height=512,
        operations_json=json.dumps(["normalize", "resize"]),
        status="completed",
        initiated_by_id=owner.id,
    ))
    for index in range(analysis_count):
        mode = "lesion" if index == 0 else "vessel_region_experimental"
        result = {
            "analysis_mode": mode,
            "target_semantics": "test-only segmentation output",
            "candidate_count": 2 if index == 0 else 0,
            "foreground_pixels": 137,
            "threshold": 0.55,
            "min_area": 20,
            "candidates": ([
                {"id": 1, "x": 10, "y": 20, "width": 8, "height": 9, "pixel_area": 54, "mean_predicted_probability": 0.81},
                {"id": 2, "x": 30, "y": 40, "width": 4, "height": 5, "pixel_area": 20, "mean_predicted_probability": 0.63},
            ] if index == 0 else []),
            "checkpoint_sha256": "a" * 64,
            "model": {
                "architecture": "UNet",
                "image_size": 256,
                "validation": {
                    "split": "stenosis/val",
                    "samples": 200,
                    "metrics": {"per_image_macro": {"dice": 0.42, "iou": 0.31}},
                },
            },
            "explainability": None,
            "artifacts": {},
        }
        db.add(StenosisAnalysis(
            id=f"{analysis_prefix}-analysis-{index}",
            case_id=case.id,
            image_id=image.id,
            initiated_by_id=owner.id,
            model_name="baseline_unet.pth",
            model_architecture="UNet",
            status="completed",
            result_json=json.dumps(result),
            artifacts_json=json.dumps({"mask": f"history-analysis-{index}_mask.png"}),
            created_at=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
        ))
    grants = [(shared_user_id, "shared"), (assigned_user_id, "assigned")]
    db.add_all([
        CaseAccess(case_id=case.id, user_id=user_id, access_type=access_type, granted_by_id=admin.id)
        for user_id, access_type in grants if user_id is not None
    ])
    db.flush()
    return case, image


def test_history_returns_owner_shared_and_assigned_records_with_filters_and_pagination(client, db_session):
    owner = make_user(db_session, "history-owner@example.com", UserRole.RESEARCHER.value)
    admin = make_user(db_session, "history-admin@example.com", UserRole.ADMINISTRATOR.value)
    shared = make_user(db_session, "history-shared@example.com", UserRole.RESEARCHER.value)
    assigned = make_user(db_session, "history-assigned@example.com", UserRole.RESEARCHER.value)
    outsider = make_user(db_session, "history-outsider@example.com", UserRole.RESEARCHER.value)
    case, _image = _seed_history(
        db_session, owner, admin, shared_user_id=shared.id, assigned_user_id=assigned.id,
    )
    db_session.commit()

    owner_token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]
    outsider_token = client.post("/api/auth/login", json={"email": outsider.email, "password": "Password123"}).json()["access_token"]
    shared_token = client.post("/api/auth/login", json={"email": shared.email, "password": "Password123"}).json()["access_token"]
    assigned_token = client.post("/api/auth/login", json={"email": assigned.email, "password": "Password123"}).json()["access_token"]

    assert client.get("/api/analyses").status_code == 401
    for token in (owner_token, shared_token, assigned_token):
        response = client.get("/api/analyses?limit=1&offset=0", headers=auth_header(token))
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert response.headers["x-total-count"] == "2"
        assert response.json()[0]["case_identifier"] == "HISTORY-CASE-1"

    mode_result = client.get("/api/analyses?limit=1&mode=vessel_region_experimental", headers=auth_header(owner_token))
    assert mode_result.status_code == 200
    assert [item["analysis_mode"] for item in mode_result.json()] == ["vessel_region_experimental"]
    assert mode_result.headers["x-total-count"] == "1"
    next_page = client.get("/api/analyses?limit=1&offset=1", headers=auth_header(owner_token))
    assert next_page.status_code == 200
    assert len(next_page.json()) == 1
    assert next_page.json()[0]["id"] != client.get("/api/analyses?limit=1", headers=auth_header(owner_token)).json()[0]["id"]
    assert client.get("/api/analyses?search=not-a-case", headers=auth_header(owner_token)).json() == []
    assert client.get("/api/analyses", headers=auth_header(outsider_token)).json() == []
    # Detail access intentionally returns 404 for a record outside this user's visible scope.
    assert client.get("/api/analyses/history-analysis-0", headers=auth_header(outsider_token)).status_code == 404
    assert client.get(f"/api/analyses/history-analysis-0", headers=auth_header(owner_token)).json()["case_id"] == case.id


def test_csv_export_uses_saved_records_and_serializes_nested_fields(client, db_session):
    owner = make_user(db_session, "csv-owner@example.com", UserRole.RESEARCHER.value)
    admin = make_user(db_session, "csv-admin@example.com", UserRole.ADMINISTRATOR.value)
    case, _image = _seed_history(db_session, owner, admin, analysis_count=1)
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]

    response = client.get(f"/api/cases/{case.id}/reports/csv", headers=auth_header(token))

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert len(rows) == 2  # One actual CSV row for each saved candidate.
    row = rows[0]
    assert row["analysis_id"] == "history-analysis-0"
    assert row["case_id"] == case.id
    assert row["case_identifier"] == "HISTORY-CASE-1"
    assert row["image_width"] == "512" and row["image_height"] == "512"
    assert row["analysis_mode"] == "lesion" and row["status"] == "completed"
    assert row["model_name"] == "baseline_unet.pth" and row["model_architecture"] == "UNet"
    assert row["checkpoint_sha256"] == "a" * 64
    assert row["foreground_pixels"] == "137" and row["candidate_count"] == "2"
    assert row["validation_split"] == "stenosis/val" and row["validation_macro_dice"] == "0.42"
    assert json.loads(row["preprocessing_operations"]) == ["normalize", "resize"]
    assert json.loads(row["preprocessing_configuration"]) == {
        "resize": [512, 512], "notes": 'clip, "contrast"\nkeep spacing',
    }
    assert row["candidate_id"] == "1" and row["predicted_probability"] == "0.81"
    assert row["preprocessing_status"] == "completed"
    assert row["reference_vessel_diameter_mm"] == ""
    assert row["minimum_lumen_diameter_mm"] == ""
    assert row["percentage_narrowing"] == ""
    assert row["severity"] == ""


def test_csv_uses_legacy_saved_validation_scores_and_keeps_unknowns_blank(client, db_session):
    owner = make_user(db_session, "csv-legacy-owner@example.com", UserRole.RESEARCHER.value)
    admin = make_user(db_session, "csv-legacy-admin@example.com", UserRole.ADMINISTRATOR.value)
    case, _image = _seed_history(db_session, owner, admin, analysis_count=1)
    analysis = db_session.query(StenosisAnalysis).filter_by(id="history-analysis-0").one()
    result = json.loads(analysis.result_json)
    result["model"].pop("validation")
    result["model"]["val_dice"] = 0.43362347699701786
    result["model"]["val_iou"] = 0.2979517287760973
    result.pop("checkpoint_sha256")
    result.pop("target_semantics")
    analysis.result_json = json.dumps(result)
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]

    response = client.get(f"/api/cases/{case.id}/reports/csv", headers=auth_header(token))

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert rows
    for row in rows:
        assert row["validation_macro_dice"] == "0.43362347699701786"
        assert row["validation_macro_iou"] == "0.2979517287760973"
        assert row["validation_split"] == ""
        assert row["validation_samples"] == ""
        assert row["checkpoint_sha256"] == ""
        assert row["target_semantics"] == ""
        assert row["reference_vessel_diameter_mm"] == ""
        assert row["minimum_lumen_diameter_mm"] == ""
        assert row["percentage_narrowing"] == ""

    pdf = client.get(f"/api/cases/{case.id}/reports/pdf", headers=auth_header(token))
    assert pdf.status_code == 200
    assert b"Stored checkpoint validation metrics" in pdf.content
    assert b"Dice 0.43362347699701786" in pdf.content
    assert b"IoU 0.2979517287760973" in pdf.content


def test_csv_export_for_case_without_analyses_returns_headers_only(client, db_session):
    owner = make_user(db_session, "csv-empty@example.com", UserRole.RESEARCHER.value)
    case = Case(case_identifier="EMPTY-CSV", patient_identifier="PSEUDO-EMPTY", imaging_modality="XCA", owner_id=owner.id)
    db_session.add(case)
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]

    response = client.get(f"/api/cases/{case.id}/reports/csv", headers=auth_header(token))

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert rows == []
    assert "analysis_id" in response.content.decode("utf-8-sig").splitlines()[0]


def test_pdf_csv_json_exports_are_case_scoped_and_permission_checked(client, db_session):
    owner = make_user(db_session, "report-owner@example.com", UserRole.RESEARCHER.value)
    other_owner = make_user(db_session, "report-other-owner@example.com", UserRole.RESEARCHER.value)
    admin = make_user(db_session, "report-admin@example.com", UserRole.ADMINISTRATOR.value)
    case, _image = _seed_history(db_session, owner, admin, analysis_count=2)
    other_case, _other_image = _seed_history(
        db_session, other_owner, admin, analysis_count=1, analysis_prefix="other", case_identifier="OTHER-CASE-1",
    )
    db_session.commit()
    owner_token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]
    other_token = client.post("/api/auth/login", json={"email": other_owner.email, "password": "Password123"}).json()["access_token"]
    owned_ids = {"history-analysis-0", "history-analysis-1"}

    assert client.get(f"/api/cases/{case.id}/reports/json").status_code == 401
    for export_format in ("json", "csv", "pdf"):
        response = client.get(f"/api/cases/{case.id}/reports/{export_format}", headers=auth_header(owner_token))
        assert response.status_code == 200, response.text
        if export_format == "json":
            records = response.json()
            assert {item["analysis"]["id"] for item in records} == owned_ids
            assert all(item["case_id"] == case.id for item in records)
            assert records[0]["preprocessing"]["configuration"]["notes"] == 'clip, "contrast"\nkeep spacing'
            assert records[0]["analysis"]["model"]["validation"]["metrics"]["per_image_macro"]["dice"] == 0.42
        elif export_format == "csv":
            assert response.headers["content-type"].startswith("text/csv")
            assert "attachment;" in response.headers["content-disposition"]
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
            assert {row["analysis_id"] for row in rows} == owned_ids
            assert {row["case_id"] for row in rows} == {case.id}
        else:
            assert response.headers["content-type"] == "application/pdf"
            assert "attachment;" in response.headers["content-disposition"]
            assert response.content.startswith(b"%PDF-1.4")
            assert case.id.encode() in response.content
            assert b"Case identifier: HISTORY-CASE-1" in response.content
            assert b"Image: angiogram.png | 512 x 512 | PNG" in response.content
            assert b"Preprocessing: completed" in response.content
            assert b"operations=[\"normalize\", \"resize\"]" in response.content
            assert b"input size=256" in response.content
            assert b"macro Dice 0.42" in response.content
            assert other_case.id.encode() not in response.content
            assert b"history-analysis-0" in response.content and b"history-analysis-1" in response.content
        assert client.get(
            f"/api/cases/{case.id}/reports/{export_format}", headers=auth_header(other_token),
        ).status_code == 404


def test_real_checkpoint_segmentation_persists_aligned_mask_overlay_and_history(client, db_session, monkeypatch, tmp_path):
    checkpoint = Path(__file__).resolve().parents[1] / "checkpoints" / "best_stenosis_unet_optimized.pth"
    source_image = Path(__file__).resolve().parents[3] / "stenosis" / "val" / "images" / "1.png"
    if not checkpoint.is_file() or not source_image.is_file():
        pytest.skip("The configured active checkpoint or local ARCADE validation sample is unavailable.")

    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    monkeypatch.setattr(analysis_api, "_model_path", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: tmp_path)
    owner = make_user(db_session, "real-inference@example.com", UserRole.RESEARCHER.value)
    token = client.post("/api/auth/login", json={"email": owner.email, "password": "Password123"}).json()["access_token"]
    headers = auth_header(token)
    created = client.post("/api/cases", json={
        "case_identifier": "REAL-INFERENCE-TEST",
        "patient_identifier": "PSEUDO-REAL-1",
        "imaging_modality": "XCA",
    }, headers=headers)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    image_bytes = source_image.read_bytes()
    uploaded = client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("1.png", image_bytes, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text

    result = client.post(f"/api/cases/{case_id}/analyze", headers=headers)

    assert result.status_code == 201, result.text
    analysis = result.json()
    assert analysis["analysis_mode"] == "lesion"
    assert analysis["model_name"] == checkpoint.name
    assert analysis["checkpoint_sha256"] == digest
    assert analysis["candidate_count"] == len(analysis["candidates"])
    assert analysis["foreground_pixels"] >= 0
    assert {"mask", "overlay", "boxes", "heatmap"} <= analysis["artifacts"].keys()

    masks = client.get(analysis["artifacts"]["mask"], headers=headers)
    overlays = client.get(analysis["artifacts"]["overlay"], headers=headers)
    assert masks.status_code == overlays.status_code == 200
    mask = cv2.imdecode(np.frombuffer(masks.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    overlay = cv2.imdecode(np.frombuffer(overlays.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert mask is not None and overlay is not None
    assert mask.shape == (512, 512)
    assert overlay.shape == (512, 512, 3)
    assert set(np.unique(mask)).issubset({0, 255})

    history = client.get("/api/analyses?search=REAL-INFERENCE-TEST", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == analysis["id"]
    assert history.json()[0]["case_identifier"] == "REAL-INFERENCE-TEST"
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == digest

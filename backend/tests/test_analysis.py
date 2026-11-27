import base64
import io
import json
import logging
import os
from pathlib import Path
import subprocess
from uuid import UUID, uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "local-test-signing-key-not-for-production-123456")
os.environ.setdefault("POSTGRES_PASSWORD", "local-test-password")

from app.api.v1.endpoints import analysis as analysis_endpoints, images as image_endpoints
from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.image import MedicalImage
from app.models.patient import Patient
from app.models.user import User
from app.services import analysis_inference
from app.services.analysis_inference import InferenceWorker
from app.services.analysis_storage import render_legacy_combined_visualization, validate_artifact_manifest


def png_bytes(size=(4, 4)):
    stream = io.BytesIO()
    Image.new("L", size, color=120).save(stream, format="PNG")
    return stream.getvalue()


def successful_fake_inference(image_path, run_directory, run_id, _settings):
    width, height = Image.open(image_path).size
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[0, 0] = 1
    display_mask = Image.fromarray(mask * 255, mode="L")
    display_mask.save(run_directory / "artery_mask.png", format="PNG")
    display_mask.save(run_directory / "stenosis_mask.png", format="PNG")
    Image.new("RGB", (width, height), color=0).save(run_directory / "candidate_overlay.png", format="PNG")
    montage = Image.new("RGB", (width * 2, (height + 30) * 2), color=(0, 0, 0))
    montage.paste((96, 96, 96), (0, height + 30, width, height + 31))
    binary_display = Image.fromarray(mask, mode="L").convert("RGB")
    montage.paste(binary_display, (width, 30))
    montage.paste(binary_display, (0, height + 60))
    montage.save(run_directory / "combined_visualization.png", format="PNG")
    candidates = {"label": "Predicted stenosis candidates; not confirmed stenoses", "candidates": []}
    (run_directory / "candidates.json").write_text(__import__("json").dumps(candidates), encoding="utf-8")
    raw_mask = mask.tobytes()
    raw_probability = np.zeros((height, width), dtype=np.float32).tobytes()
    return {
        "ok": True,
        "schema_version": 1,
        "metadata": {
            "attention_unet": {"model_id": "attention_unet", "threshold": 0.5},
            "unetpp": {"model_id": "unetpp_resnet34_stenosis", "threshold": 0.2},
            "gradcam_available": False,
            "gradcam_target_layer": "decoder.blocks.x_0_4.conv2.2",
            "gradcam_method": "segmentation-targeted Grad-CAM",
            "gradcam_unavailable_reason": "Grad-CAM unavailable in fake inference.",
            "clinical_validation": False,
            "candidate_count": 0,
            "runtime_versions": {"torch": "test", "torchvision": "test", "segmentation_models_pytorch": "test", "numpy": "test"},
            "total_pipeline_seconds": 0.03,
        },
        "model_times": {"attention_unet_seconds": 0.01, "unetpp_seconds": 0.02, "gradcam_seconds": 0.0},
        "original_size": [width, height],
        "arrays": {
            "artery_mask": {"dtype": "uint8", "shape": [height, width], "data": base64.b64encode(raw_mask).decode()},
            "stenosis_mask": {"dtype": "uint8", "shape": [height, width], "data": base64.b64encode(raw_mask).decode()},
            "stenosis_probability_map": {"dtype": "float32", "shape": [height, width], "data": base64.b64encode(raw_probability).decode()},
        },
        "artifacts": {
            filename: f"{run_id.hex}/{filename}"
            for filename in (
                "artery_mask.png", "stenosis_mask.png", "candidate_overlay.png",
                "combined_visualization.png", "candidates.json",
            )
        },
        "candidates": [],
        "percentage_narrowing": {
            "algorithm_version": "candidate-local-reference-predicted-mask-width-v4",
            "status": "unavailable",
            "coordinate_system": "original_image_pixel_grid",
            "measurement_unit": "pixel",
            "disclaimer": "Experimental predicted-mask-based narrowing estimate — not a clinically calibrated lumen measurement.",
            "measurements": [],
            "diagnostic_summary": {
                "candidate_count": 0, "counts_may_overlap": True,
                "valid_estimate_count": 0, "unavailable_count": 0,
                "insufficient_reference_sample_count": 0, "inconsistent_reference_width_count": 0,
                "branch_or_endpoint_rejection_count": 0, "missing_or_mismatched_mask_count": 0,
                "other_failure_count": 0, "failure_reason_counts": {},
            },
            "unavailable_reason": "No predicted stenosis candidates were returned.",
            "limitations": ["Widths describe thresholded predicted-mask foreground; no physical calibration is available."],
            "source_model_ids": {"artery": "attention_unet", "stenosis": "unetpp_resnet34_stenosis"},
            "source_thresholds": {"artery": 0.5, "stenosis": 0.2},
            "quality_parameters": {"minimum_candidate_overlap_fraction": 0.5},
        },
    }


def successful_fake_gradcam_inference(image_path, run_directory, run_id, settings):
    response = successful_fake_inference(image_path, run_directory, run_id, settings)
    heatmap = np.zeros((512, 512), dtype=np.uint8)
    heatmap[100:120, 150:170] = 255
    Image.fromarray(heatmap, mode="L").save(run_directory / "gradcam.png", format="PNG")
    response["metadata"]["gradcam_available"] = True
    response["metadata"]["gradcam_unavailable_reason"] = None
    response["model_times"]["gradcam_seconds"] = 0.04
    response["artifacts"]["gradcam.png"] = f"{run_id.hex}/gradcam.png"
    return response


def successful_fake_severity_inference(image_path, run_directory, run_id, settings):
    response = successful_fake_inference(image_path, run_directory, run_id, settings)
    response["candidates"] = [
        {"candidate_id": 1, "label": "Predicted stenosis candidate 1"},
        {"candidate_id": 2, "label": "Predicted stenosis candidate 2"},
    ]
    response["metadata"]["candidate_count"] = 2
    response["percentage_narrowing"] = {
        **response["percentage_narrowing"],
        "status": "available",
        "unavailable_reason": None,
        "measurements": [
            {
                "candidate_id": 2, "status": "available",
                "reference_predicted_mask_width_px": 100.0,
                "minimum_candidate_predicted_mask_width_px": 30.0,
                "estimated_narrowing_percent": 70.0,
                "diagnostics": {
                    "estimator_version": "candidate-local-reference-predicted-mask-width-v4",
                    "candidate_id": 2,
                    "associated_artery_component_id": 1,
                    "candidate_width_px": 30.0,
                    "reference_side_1_median_width_px": 100.0,
                    "reference_side_2_median_width_px": 100.0,
                    "reference_side_1_sample_count": 8,
                    "reference_side_2_sample_count": 8,
                    "sampling_stop_reasons": ["window_limit", "window_limit"],
                    "reference_width_px": 100.0,
                    "calculated_percentage": 70.0,
                    "sampling_rejection_reason": None,
                },
            },
            {
                "candidate_id": 1, "status": "available",
                "reference_predicted_mask_width_px": 100.0,
                "minimum_candidate_predicted_mask_width_px": 74.9,
                "estimated_narrowing_percent": 25.1,
                "diagnostics": {
                    "estimator_version": "candidate-local-reference-predicted-mask-width-v4",
                    "candidate_id": 1,
                    "associated_artery_component_id": 1,
                    "candidate_width_px": 74.9,
                    "reference_side_1_median_width_px": 100.0,
                    "reference_side_2_median_width_px": 100.0,
                    "reference_side_1_sample_count": 8,
                    "reference_side_2_sample_count": 8,
                    "sampling_stop_reasons": ["window_limit", "window_limit"],
                    "reference_width_px": 100.0,
                    "calculated_percentage": 25.1,
                    "sampling_rejection_reason": None,
                },
            },
        ],
        "diagnostic_summary": {
            "candidate_count": 2, "counts_may_overlap": True,
            "valid_estimate_count": 2, "unavailable_count": 0,
            "insufficient_reference_sample_count": 0, "inconsistent_reference_width_count": 0,
            "branch_or_endpoint_rejection_count": 0, "missing_or_mismatched_mask_count": 0,
            "other_failure_count": 0, "failure_reason_counts": {},
        },
    }
    (run_directory / "candidates.json").write_text(json.dumps({"candidates": response["candidates"]}), encoding="utf-8")
    return response


def fake_non_smaller_candidate_width_inference(image_path, run_directory, run_id, settings):
    response = successful_fake_inference(image_path, run_directory, run_id, settings)
    response["candidates"] = [{
        "candidate_id": 1,
        "label": "Predicted stenosis candidate 1",
        "bbox": [0, 0, 1, 1],
        "centroid": [0.5, 0.5],
        "area_pixels": 1,
        "mean_probability": 0.8,
    }]
    response["metadata"]["candidate_count"] = 1
    response["percentage_narrowing"] = {
        **response["percentage_narrowing"],
        "status": "unavailable",
        "unavailable_reason": "No candidate had a predicted-mask width smaller than its reference artery-mask width.",
        "measurements": [{
            "candidate_id": 1,
            "status": "unavailable",
            "unavailable_reason": "candidate_predicted_mask_width_not_smaller_than_reference",
            "diagnostics": {
                "estimator_version": "candidate-local-reference-predicted-mask-width-v4",
                "candidate_id": 1,
                "associated_artery_component_id": 1,
                "candidate_width_px": 12.0,
                "candidate_centerline_sample_count": 10,
                "candidate_overlap_fraction": 1.0,
                "artery_component_dominance": 1.0,
                "reference_side_1_median_width_px": 12.0,
                "reference_side_2_median_width_px": 12.0,
                "reference_side_1_sample_count": 8,
                "reference_side_2_sample_count": 8,
                "sampling_stop_reasons": ["window_limit", "window_limit"],
                "reference_width_px": 12.0,
                "reference_window_pixels": 24.0,
                "calculated_percentage": None,
                "sampling_rejection_reason": "candidate_predicted_mask_width_not_smaller_than_reference",
            },
        }],
        "diagnostic_summary": {
            "candidate_count": 1, "counts_may_overlap": True,
            "valid_estimate_count": 0, "unavailable_count": 1,
            "insufficient_reference_sample_count": 0, "inconsistent_reference_width_count": 0,
            "branch_or_endpoint_rejection_count": 0, "missing_or_mismatched_mask_count": 0,
            "other_failure_count": 1,
            "failure_reason_counts": {"candidate_predicted_mask_width_not_smaller_than_reference": 1},
        },
    }
    (run_directory / "candidates.json").write_text(json.dumps({"candidates": response["candidates"]}), encoding="utf-8")
    return response


def configured_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "private-analysis"
    settings = Settings(upload_directory=upload_dir, analysis_output_directory=output_dir)
    monkeypatch.setattr(image_endpoints, "get_settings", lambda: settings)
    monkeypatch.setattr(analysis_endpoints, "get_settings", lambda: settings)
    return engine, test_session, TestClient(app), upload_dir, output_dir


def test_backend_accepts_gradcam_available_or_unavailable_worker_responses(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(png_bytes())
    run_id = uuid4()
    run_directory = tmp_path / run_id.hex
    run_directory.mkdir()
    unavailable = successful_fake_inference(source, run_directory, run_id, None)
    InferenceWorker._validate_response(unavailable, run_id, source)

    mismatch = successful_fake_inference(source, tmp_path, run_id, None)
    mismatch["percentage_narrowing"]["source_thresholds"]["stenosis"] = 0.21
    with pytest.raises(ValueError, match="thresholds do not match"):
        InferenceWorker._validate_response(mismatch, run_id, source)

    available = successful_fake_inference(source, run_directory, run_id, None)
    available["metadata"]["gradcam_available"] = True
    available["metadata"]["gradcam_unavailable_reason"] = None
    available["artifacts"]["gradcam.png"] = f"{run_id.hex}/gradcam.png"
    InferenceWorker._validate_response(available, run_id, source)

    available["artifacts"].pop("gradcam.png")
    with pytest.raises(ValueError, match="artifact manifest"):
        InferenceWorker._validate_response(available, run_id, source)


def test_backend_validates_candidate_measurement_provenance_and_formula(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(png_bytes())
    run_id = uuid4()
    response = successful_fake_inference(source, tmp_path, run_id, None)
    response["candidates"] = [{"candidate_id": 1, "label": "Predicted stenosis candidate 1"}]
    response["metadata"]["candidate_count"] = 1
    response["percentage_narrowing"]["status"] = "available"
    response["percentage_narrowing"]["measurements"] = [{
        "candidate_id": 1,
        "status": "available",
        "reference_predicted_mask_width_px": 12.0,
        "minimum_candidate_predicted_mask_width_px": 9.0,
        "estimated_narrowing_percent": 25.0,
    }]

    InferenceWorker._validate_response(response, run_id, source)

    response["percentage_narrowing"]["measurements"][0]["estimated_narrowing_percent"] = 30.0
    with pytest.raises(ValueError, match="does not match its stored widths"):
        InferenceWorker._validate_response(response, run_id, source)


def test_backend_accepts_specific_unavailable_candidate_width_reason(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(png_bytes())
    run_id = uuid4()
    run_directory = tmp_path / run_id.hex
    run_directory.mkdir()
    response = fake_non_smaller_candidate_width_inference(source, run_directory, run_id, None)

    InferenceWorker._validate_response(response, run_id, source)


def test_gradcam_manifest_is_optional_but_png_dimensions_are_strict(tmp_path):
    run_id = uuid4()
    output_dir = tmp_path / "analysis"
    run_directory = output_dir / run_id.hex
    run_directory.mkdir(parents=True)
    names = ("artery_mask.png", "stenosis_mask.png", "candidate_overlay.png", "combined_visualization.png")
    for name in names:
        mode = "RGB" if name in {"candidate_overlay.png", "combined_visualization.png"} else "L"
        Image.new(mode, (4, 4), color=0).save(run_directory / name, format="PNG")
    (run_directory / "candidates.json").write_text('{"candidates": []}', encoding="utf-8")
    required = {name: f"{run_id.hex}/{name}" for name in (*names, "candidates.json")}
    assert set(validate_artifact_manifest(output_dir, run_id, required, expected_image_size=(4, 4))) == set(required)

    Image.new("L", (512, 512), color=0).save(run_directory / "gradcam.png", format="PNG")
    with_gradcam = {**required, "gradcam.png": f"{run_id.hex}/gradcam.png"}
    assert "gradcam.png" in validate_artifact_manifest(output_dir, run_id, with_gradcam, expected_image_size=(4, 4))

    Image.new("L", (256, 256), color=0).save(run_directory / "gradcam.png", format="PNG")
    with pytest.raises(ValueError, match="512x512"):
        validate_artifact_manifest(output_dir, run_id, with_gradcam, expected_image_size=(4, 4))


def test_analysis_persists_metadata_and_protects_artifacts(tmp_path, monkeypatch):
    engine, session_factory, client, upload_dir, output_dir = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis_endpoints.inference_worker, "run", successful_fake_inference)
    try:
        with session_factory() as db:
            owner = User(email="analysis-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="analysis-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            admin = User(email="analysis-admin@example.com", password_hash=hash_password("test-password-long"), role="admin")
            db.add_all([owner, other, admin])
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="analysis-test-patient")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="analysis-test-case")
            db.add(case)
            db.flush()
            upload_dir.mkdir(parents=True)
            source = png_bytes()
            (upload_dir / "test.png").write_bytes(source)
            image = MedicalImage(
                case_id=case.id,
                uploaded_by_id=owner.id,
                storage_key="test.png",
                original_filename="test.png",
                media_type="image/png",
                size_bytes=len(source),
                sha256="0" * 64,
            )
            db.add(image)
            db.commit()
            owner_id, other_id, admin_id, case_id, image_id = owner.id, other.id, admin.id, case.id, image.id

        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
        admin_headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
        runs_url = f"/api/v1/cases/{case_id}/analysis-runs"
        assert client.get(runs_url).status_code == 401
        assert client.post(f"/api/v1/cases/{case_id}/analysis-runs", json={"image_id": str(image_id)}).status_code == 401
        assert client.post(
            f"/api/v1/cases/{case_id}/analysis-runs", headers=other_headers, json={"image_id": str(image_id)}
        ).status_code == 404
        assert client.post(
            f"/api/v1/cases/{case_id}/analysis-runs", headers=owner_headers,
            json={"image_id": str(UUID(int=0))},
        ).status_code == 404

        created = client.post(
            f"/api/v1/cases/{case_id}/analysis-runs", headers=owner_headers, json={"image_id": str(image_id)}
        )
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        assert created.json()["status"] == "completed"
        assert created.json()["result_metadata"]["models"]["gradcam_available"] is False
        assert created.json()["result_metadata"]["percentage_narrowing"]["status"] == "unavailable"
        assert "stenosis_probability_map" not in str(created.json()["result_metadata"])
        with session_factory() as db:
            saved = db.get(AnalysisRun, UUID(run_id))
            assert saved is not None and saved.status == "completed"
            assert saved.result_metadata["candidate_label"].startswith("Predicted")
            assert saved.result_metadata["percentage_narrowing"]["disclaimer"].startswith("Experimental predicted-mask")
            assert "arrays" not in saved.result_metadata
            assert saved.duration_seconds is not None
        status_response = client.get(f"/api/v1/analysis-runs/{run_id}", headers=owner_headers)
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"
        results = client.get(f"/api/v1/analysis-runs/{run_id}/results", headers=owner_headers)
        assert results.status_code == 200
        assert results.json()["metadata"]["percentage_narrowing"]["status"] == "unavailable"
        assert results.json()["source_image_url"] == f"/api/v1/images/{image_id}/content"
        artifact_url = results.json()["artifacts"]["artery_mask.png"]
        artifact_response = client.get(artifact_url, headers=owner_headers)
        assert artifact_response.status_code == 200
        assert artifact_response.headers["cache-control"] == "private, no-store"
        assert client.get(artifact_url, headers=other_headers).status_code == 404
        combined_path = output_dir / UUID(run_id).hex / "combined_visualization.png"
        stored_combined_before = combined_path.read_bytes()
        combined_url = results.json()["artifacts"]["combined_visualization.png"]
        combined_response = client.get(combined_url, headers=owner_headers)
        assert combined_response.status_code == 200
        served_combined = np.asarray(Image.open(io.BytesIO(combined_response.content)).convert("L"))
        source_width, source_height = Image.open(io.BytesIO(source)).size
        assert served_combined[30, source_width] == 255
        assert served_combined[source_height + 60, 0] == 255
        assert served_combined[source_height + 30, 0] == 96
        assert combined_path.read_bytes() == stored_combined_before
        assert client.get(f"/api/v1/analysis-runs/{run_id}", headers=other_headers).status_code == 404
        owner_runs = client.get(runs_url, headers=owner_headers)
        assert owner_runs.status_code == 200
        assert [item["id"] for item in owner_runs.json()] == [run_id]
        assert client.get(runs_url, headers=other_headers).status_code == 404
        admin_runs = client.get(runs_url, headers=admin_headers)
        assert admin_runs.status_code == 200
        assert [item["id"] for item in admin_runs.json()] == [run_id]
        assert len(list((output_dir / UUID(run_id).hex).iterdir())) == 5

        monkeypatch.setattr(analysis_endpoints.inference_worker, "run", successful_fake_gradcam_inference)
        gradcam_created = client.post(
            runs_url, headers=owner_headers, json={"image_id": str(image_id)}
        )
        assert gradcam_created.status_code == 201, gradcam_created.text
        gradcam_run_id = gradcam_created.json()["id"]
        assert gradcam_created.json()["result_metadata"]["models"]["gradcam_available"] is True
        gradcam_results = client.get(
            f"/api/v1/analysis-runs/{gradcam_run_id}/results", headers=owner_headers
        )
        gradcam_url = gradcam_results.json()["artifacts"]["gradcam.png"]
        gradcam_response = client.get(gradcam_url, headers=owner_headers)
        assert gradcam_response.status_code == 200
        assert gradcam_response.headers["cache-control"] == "private, no-store"
        with Image.open(io.BytesIO(gradcam_response.content)) as gradcam_image:
            assert gradcam_image.size == (512, 512)
            assert gradcam_image.mode == "L"
        assert client.get(gradcam_url, headers=other_headers).status_code == 404
        assert len(list((output_dir / UUID(gradcam_run_id).hex).iterdir())) == 6
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_analysis_failure_is_logged_safely_persisted_and_can_be_retried(tmp_path, monkeypatch, caplog):
    engine, session_factory, client, upload_dir, _output_dir = configured_client(tmp_path, monkeypatch)
    try:
        with session_factory() as db:
            owner = User(email="analysis-retry@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add(owner)
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="analysis-retry-patient")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="analysis-retry-case")
            db.add(case)
            db.flush()
            upload_dir.mkdir(parents=True)
            source = png_bytes()
            (upload_dir / "retry.png").write_bytes(source)
            image = MedicalImage(
                case_id=case.id,
                uploaded_by_id=owner.id,
                storage_key="retry.png",
                original_filename="retry.png",
                media_type="image/png",
                size_bytes=len(source),
                sha256="1" * 64,
            )
            db.add(image)
            db.commit()
            owner_id, case_id, image_id = owner.id, case.id, image.id

        headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        monkeypatch.setattr(
            analysis_endpoints.inference_worker,
            "run",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("private internal detail")),
        )
        with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.analysis"):
            failed = client.post(f"/api/v1/cases/{case_id}/analysis-runs", headers=headers, json={"image_id": str(image_id)})
        assert failed.status_code == 201
        assert failed.json()["status"] == "failed"
        assert failed.json()["failure_code"] == "inference_failed"
        assert "private internal detail" not in failed.text
        assert "Synchronous analysis failed (run_id=" in caplog.text
        assert "exception_type=RuntimeError" in caplog.text
        assert "private internal detail" not in caplog.text

        monkeypatch.setattr(analysis_endpoints.inference_worker, "run", successful_fake_inference)
        retried = client.post(f"/api/v1/cases/{case_id}/analysis-runs", headers=headers, json={"image_id": str(image_id)})
        assert retried.status_code == 201
        assert retried.json()["status"] == "completed"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ml_worker_startup_suppresses_private_stderr_and_auth_environment(tmp_path, monkeypatch):
    worker_root = tmp_path / "repo"
    worker_script = worker_root / "ml" / "inference" / "worker.py"
    worker_script.parent.mkdir(parents=True)
    worker_script.write_text("# test placeholder", encoding="utf-8")
    executable = tmp_path / "ml-python"
    executable.write_text("test placeholder", encoding="utf-8")
    monkeypatch.setattr(InferenceWorker, "_repo_root", staticmethod(lambda: worker_root))
    spawned = {}

    class RunningProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    process = RunningProcess()

    def fake_popen(command, **kwargs):
        spawned["command"] = command
        spawned.update(kwargs)
        return process

    monkeypatch.setattr(analysis_inference.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(InferenceWorker, "_request", staticmethod(lambda *_args, **_kwargs: b"{}"))
    worker = InferenceWorker()
    settings = Settings(
        secret_key="local-test-signing-key-not-for-production-123456",
        ml_python_executable=executable,
        upload_directory=tmp_path / "uploads",
        analysis_output_directory=tmp_path / "outputs",
    )
    worker._start(settings)

    assert spawned["stderr"] == subprocess.DEVNULL
    assert spawned["stdin"] == subprocess.DEVNULL
    assert "SECRET_KEY" not in spawned["env"]
    assert "DATABASE_URL" not in spawned["env"]
    worker.close()


def test_ml_worker_rejects_missing_configured_executable_before_startup(tmp_path, monkeypatch):
    worker_root = tmp_path / "repository"
    worker_script = worker_root / "ml" / "inference" / "worker.py"
    worker_script.parent.mkdir(parents=True)
    worker_script.write_text("# test placeholder", encoding="utf-8")
    missing_executable = tmp_path / "missing-ml-python.exe"
    monkeypatch.setattr(InferenceWorker, "_repo_root", staticmethod(lambda: worker_root))
    worker = InferenceWorker()
    settings = Settings(
        secret_key="local-test-signing-key-not-for-production-123456",
        ml_python_executable=missing_executable,
    )

    with pytest.raises(analysis_inference.InferenceUnavailable, match="isolated ML runtime is not configured"):
        worker._start(settings)

    assert worker._process is None
    assert worker._port is None


def test_linux_backend_rejects_windows_ml_executable_with_safe_actionable_error():
    if os.name == "nt":
        pytest.skip("This compatibility check is for the Linux/WSL backend runtime")
    with pytest.raises(analysis_inference.InferenceUnavailable, match="Windows ML executable"):
        analysis_inference._resolve_ml_executable(Path(r"C:\Users\example\ml\.venv\Scripts\python.exe"))


def test_ml_executable_resolution_preserves_virtualenv_symlink(tmp_path, monkeypatch):
    target = tmp_path / "base-python"
    target.write_text("interpreter placeholder")
    executable = tmp_path / "env" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.write_text("virtual environment interpreter placeholder")
    configured_path = Path(os.path.abspath(executable))
    original_resolve = Path.resolve

    def resolve_simulated_venv_symlink(path, *args, **kwargs):
        if path == executable:
            return target
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_simulated_venv_symlink)

    resolved = analysis_inference._resolve_ml_executable(executable)

    assert resolved == configured_path
    assert resolved != target


def test_severity_is_persisted_per_candidate_and_returned_owner_scoped(tmp_path, monkeypatch):
    engine, session_factory, client, upload_dir, _output_dir = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis_endpoints.inference_worker, "run", successful_fake_severity_inference)
    try:
        with session_factory() as db:
            owner = User(email="severity-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            other = User(email="severity-other@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add_all([owner, other])
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="severity-test-patient")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="severity-test-case")
            db.add(case)
            db.flush()
            upload_dir.mkdir(parents=True)
            source = png_bytes()
            (upload_dir / "severity-test.png").write_bytes(source)
            image = MedicalImage(
                case_id=case.id,
                uploaded_by_id=owner.id,
                storage_key="severity-test.png",
                original_filename="severity-test.png",
                media_type="image/png",
                size_bytes=len(source),
                sha256="2" * 64,
            )
            db.add(image)
            db.commit()
            owner_id, other_id, case_id, image_id = owner.id, other.id, case.id, image.id

        owner_headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
        created = client.post(
            f"/api/v1/cases/{case_id}/analysis-runs",
            headers=owner_headers,
            json={"image_id": str(image_id)},
        )
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        saved_narrowing = created.json()["result_metadata"]["percentage_narrowing"]
        assert saved_narrowing["algorithm_version"] == "candidate-local-reference-predicted-mask-width-v4"
        assert [item["estimated_narrowing_percent"] for item in saved_narrowing["measurements"]] == [70.0, 25.1]
        assert saved_narrowing["diagnostic_summary"]["valid_estimate_count"] == 2
        assert saved_narrowing["measurements"][0]["diagnostics"]["candidate_id"] == 2
        assert saved_narrowing["measurements"][0]["diagnostics"]["reference_side_1_sample_count"] == 8
        saved_assessment = created.json()["result_metadata"]["severity_assessment"]
        assert saved_assessment["algorithm_version"] == "task5-user-specified-thresholds-v1"
        assert [(item["candidate_id"], item["severity"]) for item in saved_assessment["measurements"]] == [
            (1, "Mild"), (2, "Critical"),
        ]
        with session_factory() as db:
            saved_run = db.get(AnalysisRun, UUID(run_id))
            assert saved_run.result_metadata["severity_assessment"] == saved_assessment

        results = client.get(f"/api/v1/analysis-runs/{run_id}/results", headers=owner_headers)
        assert results.status_code == 200
        assert results.json()["metadata"]["percentage_narrowing"] == saved_narrowing
        assert results.json()["metadata"]["percentage_narrowing"]["diagnostic_summary"] == saved_narrowing["diagnostic_summary"]
        assert results.json()["metadata"]["severity_assessment"] == saved_assessment
        assert client.get(f"/api/v1/analysis-runs/{run_id}/results", headers=other_headers).status_code == 404

        # Simulate a pre-Task-5 saved result: API retrieval remains valid without this optional key.
        with session_factory() as db:
            saved_run = db.get(AnalysisRun, UUID(run_id))
            saved_run.result_metadata = {
                key: value for key, value in saved_run.result_metadata.items()
                if key != "severity_assessment"
            }
            db.commit()
        legacy_results = client.get(f"/api/v1/analysis-runs/{run_id}/results", headers=owner_headers)
        assert legacy_results.status_code == 200
        assert "severity_assessment" not in legacy_results.json()["metadata"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_non_smaller_candidate_width_reason_is_saved_and_severity_stays_unavailable(tmp_path, monkeypatch):
    engine, session_factory, client, upload_dir, _output_dir = configured_client(tmp_path, monkeypatch)
    monkeypatch.setattr(analysis_endpoints.inference_worker, "run", fake_non_smaller_candidate_width_inference)
    try:
        with session_factory() as db:
            owner = User(email="width-diagnostic-owner@example.com", password_hash=hash_password("test-password-long"), role="user")
            db.add(owner)
            db.flush()
            patient = Patient(owner_id=owner.id, patient_ref="width-diagnostic-patient")
            db.add(patient)
            db.flush()
            case = Case(owner_id=owner.id, patient_id=patient.id, case_ref="width-diagnostic-case")
            db.add(case)
            db.flush()
            upload_dir.mkdir(parents=True)
            source = png_bytes()
            (upload_dir / "width-diagnostic.png").write_bytes(source)
            image = MedicalImage(
                case_id=case.id,
                uploaded_by_id=owner.id,
                storage_key="width-diagnostic.png",
                original_filename="width-diagnostic.png",
                media_type="image/png",
                size_bytes=len(source),
                sha256="3" * 64,
            )
            db.add(image)
            db.commit()
            owner_id, case_id, image_id = owner.id, case.id, image.id

        headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
        created = client.post(
            f"/api/v1/cases/{case_id}/analysis-runs",
            headers=headers,
            json={"image_id": str(image_id)},
        )
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        result_meta = created.json()["result_metadata"]
        assert result_meta["percentage_narrowing"]["measurements"][0]["unavailable_reason"] == (
            "candidate_predicted_mask_width_not_smaller_than_reference"
        )
        diagnostic = result_meta["percentage_narrowing"]["measurements"][0]["diagnostics"]
        assert diagnostic["candidate_width_px"] == diagnostic["reference_width_px"] == 12.0
        assert diagnostic["sampling_rejection_reason"] == (
            "candidate_predicted_mask_width_not_smaller_than_reference"
        )
        assert result_meta["percentage_narrowing"]["diagnostic_summary"]["other_failure_count"] == 1
        assert result_meta["severity_assessment"]["status"] == "unavailable"
        assert result_meta["severity_assessment"]["measurements"] == [{
            "candidate_id": 1,
            "status": "unavailable",
            "reason": "saved_narrowing_estimate_unavailable",
        }]
        assert "severity" not in result_meta["severity_assessment"]["measurements"][0]

        with session_factory() as db:
            saved = db.get(AnalysisRun, UUID(run_id))
            assert saved.result_metadata["percentage_narrowing"]["measurements"][0]["unavailable_reason"] == (
                "candidate_predicted_mask_width_not_smaller_than_reference"
            )
        results = client.get(f"/api/v1/analysis-runs/{run_id}/results", headers=headers)
        assert results.status_code == 200
        assert results.json()["metadata"]["percentage_narrowing"]["measurements"][0]["unavailable_reason"] == (
            "candidate_predicted_mask_width_not_smaller_than_reference"
        )
        assert results.json()["metadata"]["percentage_narrowing"]["measurements"][0]["diagnostics"] == diagnostic
        assert results.json()["metadata"]["severity_assessment"]["status"] == "unavailable"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_legacy_combined_visualization_is_repaired_only_in_memory(tmp_path):
    path = tmp_path / "combined_visualization.png"
    image = Image.new("RGB", (8, 76), color=(0, 0, 0))
    image.paste((96, 96, 96), (0, 30, 4, 38))
    # A rendered label belongs to the second-row title band, above its mask.
    image.paste((96, 96, 96), (0, 45, 4, 46))
    image.putpixel((5, 32), (1, 1, 1))
    image.putpixel((1, 71), (1, 1, 1))
    image.save(path, format="PNG")
    original = path.read_bytes()

    repaired_content = render_legacy_combined_visualization(path)

    assert repaired_content is not None
    repaired = Image.open(io.BytesIO(repaired_content)).convert("RGB")
    assert repaired.getpixel((5, 32)) == (255, 255, 255)
    assert repaired.getpixel((1, 71)) == (255, 255, 255)
    assert repaired.getpixel((1, 31)) == (96, 96, 96)
    assert repaired.getpixel((1, 45)) == (96, 96, 96)
    assert path.read_bytes() == original

    modern = Image.new("RGB", (8, 76), color=(0, 0, 0))
    modern.paste((255, 255, 255), (4, 30, 8, 38))
    modern.paste((255, 255, 255), (0, 68, 4, 76))
    modern_path = tmp_path / "modern_combined.png"
    modern.save(modern_path, format="PNG")
    assert render_legacy_combined_visualization(modern_path) is None

import hashlib
import json

import cv2
import numpy as np
import pytest
from PIL import Image

from app.api import analysis as analysis_api
from app.arcade_ml.ground_truth_comparison import (
    evaluate_masks,
    find_exact_training_annotation,
)
from app.core.permissions import UserRole
from app.models.user import User
from tests.conftest import auth_header, register_and_login


def _make_train_split(root, image_bytes, *, file_name="1.png", image_id=1, width=64, height=64):
    image_dir = root / "images"
    annotation_dir = root / "annotations"
    image_dir.mkdir(parents=True)
    annotation_dir.mkdir()
    (image_dir / file_name).write_bytes(image_bytes)
    payload = {
        "images": [{"id": image_id, "file_name": file_name, "width": width, "height": height}],
        "categories": [{"id": 26, "name": "stenosis"}],
        "annotations": [{"id": 19, "image_id": image_id, "category_id": 26,
                         "segmentation": [[1, 2, 3, 2, 3, 5, 1, 5]],
                         "area": 12, "bbox": [1, 2, 3, 4], "iscrowd": 0}],
    }
    (annotation_dir / "train.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_exact_training_annotation_requires_filename_and_identical_file_content(tmp_path, png_bytes):
    train = _make_train_split(tmp_path / "train", png_bytes)
    uploaded = tmp_path / "uploaded" / "1.png"
    uploaded.parent.mkdir()
    uploaded.write_bytes(png_bytes)
    record, annotations, source, digest = find_exact_training_annotation(uploaded, "1.png", train)
    assert record["id"] == 1 and record["width"] == record["height"] == 64
    assert [item["id"] for item in annotations] == [19]
    assert [item["category_id"] for item in annotations] == [26]
    assert source == train / "images" / "1.png"
    assert digest == hashlib.sha256(png_bytes).hexdigest()

    renamed = tmp_path / "uploaded" / "different.png"
    renamed.write_bytes(png_bytes)
    with pytest.raises(ValueError, match="No exact filename/content match"):
        find_exact_training_annotation(renamed, "different.png", train)


def test_mask_metrics_and_components_are_exact_and_reject_alignment_errors():
    ground = np.zeros((8, 8), dtype=bool)
    prediction = np.zeros_like(ground)
    ground[2:5, 1:4] = True
    prediction[2:5, 1:4] = True
    candidate = [{"id": 5, "x": 1, "y": 2, "width": 3, "height": 3, "pixel_area": 9}]
    metrics, components = evaluate_masks(ground, prediction, candidate)
    assert (metrics["tp"], metrics["fp"], metrics["fn"]) == (9, 0, 0)
    assert (metrics["dice"], metrics["iou"], metrics["precision"], metrics["recall"]) == (1, 1, 1, 1)
    assert components[0]["overlaps_ground_truth"] is True
    assert components[0]["ground_truth_overlap_pixels"] == 9
    with pytest.raises(ValueError, match="aligned 2D"):
        evaluate_masks(ground, np.zeros((7, 8)), candidate)
    with pytest.raises(ValueError, match="cannot be aligned"):
        evaluate_masks(ground, prediction, [{**candidate[0], "x": 0}])


def test_case_ground_truth_comparison_is_authorized_aligned_and_persisted(
    client, db_session, monkeypatch, tmp_path, png_bytes,
):
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"test checkpoint")
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    monkeypatch.setattr(analysis_api, "_model_path", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: analysis_api.StenosisAnalyzer.__new__(analysis_api.StenosisAnalyzer))
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: analysis_dir)
    train_dir = _make_train_split(tmp_path / "stenosis-train", png_bytes)
    monkeypatch.setattr(analysis_api, "stenosis_split_dir", lambda split: train_dir)

    token, user_data = register_and_login(client, "ground-truth-owner@example.com")
    headers = auth_header(token)
    case = client.post("/api/cases", json={
        "case_identifier": "GT-CASE", "patient_identifier": "SYNTH-GT", "imaging_modality": "CTA",
    }, headers=headers)
    assert case.status_code == 201, case.text
    case_id = case.json()["id"]
    upload = client.post(f"/api/cases/{case_id}/upload",
                         files={"file": ("1.png", png_bytes, "image/png")}, headers=headers)
    assert upload.status_code == 200, upload.text
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: type("Fake", (), {
        "analyze": lambda self, image: {
            "images": {"mask_png": b"fake mask", "overlay_png": b"fake overlay",
                       "boxes_png": b"fake boxes", "heatmap_png": b"fake heatmap"},
            "model": {"resolved_architecture": "test_model"}, "n_candidates": 1,
            "foreground_pixels": 12, "threshold": 0.5, "min_area": 20,
            "candidates": [{"id": 1, "x": 1, "y": 2, "width": 3, "height": 4, "pixel_area": 12}],
            "limitations": [],
        }
    })())
    analysis = client.post(f"/api/cases/{case_id}/analyze", headers=headers)
    assert analysis.status_code == 201, analysis.text
    analysis_id = analysis.json()["id"]
    predicted = np.zeros((64, 64), dtype=np.uint8)
    predicted[2:6, 1:4] = 255
    ok, encoded = cv2.imencode(".png", predicted)
    assert ok
    (analysis_dir / f"{analysis_id}_mask.png").write_bytes(encoded.tobytes())

    assert client.post(f"/api/analyses/{analysis_id}/ground-truth").status_code == 401
    forbidden = client.post(f"/api/analyses/{analysis_id}/ground-truth", headers=headers)
    assert forbidden.status_code == 403
    db_user = db_session.get(User, user_data["id"])
    db_user.role = UserRole.DATA_SCIENTIST.value
    db_session.commit()
    compared = client.post(f"/api/analyses/{analysis_id}/ground-truth", headers=headers)
    assert compared.status_code == 200, compared.text
    result = compared.json()["ground_truth_comparison"]
    assert result["dataset_split"] == "stenosis/train"
    assert result["image_id"] == 1
    assert result["annotation_ids"] == [19]
    assert result["category_ids"] == [26]
    assert result["width"] == result["height"] == 64
    assert result["alignment_verified"] is True
    assert result["metrics"]["dice"] == 1
    assert result["metrics"]["tp"] == 12
    assert result["predicted_components"][0]["overlaps_ground_truth"] is True
    comparison_url = compared.json()["artifacts"]["ground_truth_comparison"]
    preview = client.get(comparison_url, headers=headers)
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
    persisted = client.get(f"/api/analyses/{analysis_id}", headers=headers).json()
    assert persisted["ground_truth_comparison"] == result
    report = client.get(f"/api/cases/{case_id}/reports/json", headers=headers).json()
    assert report[0]["analysis"]["ground_truth_comparison"]["metrics"]["dice"] == 1
    csv = client.get(f"/api/cases/{case_id}/reports/csv", headers=headers)
    assert "ground_truth_dice" in csv.text and "1.0" in csv.text
    pdf = client.get(f"/api/cases/{case_id}/reports/pdf", headers=headers)
    assert b"ARCADE pixel comparison" in pdf.content


def test_exact_filename_with_different_bytes_is_not_guessed(tmp_path, png_bytes):
    train = _make_train_split(tmp_path / "train", png_bytes)
    uploaded = tmp_path / "uploaded.png"
    uploaded.write_bytes(png_bytes + b"changed")
    with pytest.raises(ValueError, match="No exact filename/content match"):
        find_exact_training_annotation(uploaded, "1.png", train)


def test_annotation_dimensions_must_match_source(tmp_path, png_bytes):
    train = _make_train_split(tmp_path / "train", png_bytes, width=63, height=64)
    uploaded = tmp_path / "1.png"
    uploaded.write_bytes(png_bytes)
    with pytest.raises(ValueError, match="dimensions do not align"):
        find_exact_training_annotation(uploaded, "1.png", train)


def test_wrong_category_26_semantics_are_rejected(tmp_path, png_bytes):
    train = _make_train_split(tmp_path / "train", png_bytes)
    payload_path = train / "annotations" / "train.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["categories"][0]["name"] = "vessel"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    uploaded = tmp_path / "1.png"
    uploaded.write_bytes(png_bytes)
    with pytest.raises(ValueError, match="not explicitly identified as stenosis"):
        find_exact_training_annotation(uploaded, "1.png", train)

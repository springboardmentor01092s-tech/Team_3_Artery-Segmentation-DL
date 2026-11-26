from app.api import analysis as analysis_api
from app.core.permissions import UserRole
import numpy as np
import pytest
from types import SimpleNamespace

from tests.conftest import auth_header, make_user, register_and_login


def test_pdf_report_wraps_long_lines_and_has_valid_cross_reference_table():
    pdf = analysis_api._simple_pdf([
        "Artery segmentation research report",
        "Report detail: " + "saved model and validation metadata " * 10 + "end-marker",
        *(f"additional page line {index}" for index in range(35)),
    ])

    assert pdf.startswith(b"%PDF-1.4")
    assert b"/Count 2" in pdf
    assert b"(end-marker) Tj" in pdf
    assert pdf.count(b"0 -20 Td") >= 2
    import re
    startxref = int(re.search(rb"startxref\n(\d+)\n%%EOF", pdf).group(1))
    xref = pdf[startxref:]
    assert xref.startswith(b"xref\n")
    lines = xref.splitlines()
    object_count = int(lines[1].split()[1])
    entries = lines[3:3 + object_count - 1]
    assert len(entries) == object_count - 1
    for entry in entries:
        offset = int(entry[:10])
        assert re.match(rb"\d+ 0 obj\n", pdf[offset:])


class FakeAnalyzer:
    def analyze(self, image):
        assert image.shape[:2] == (64, 64)
        return {
            "images": {"mask_png": b"fake mask", "overlay_png": b"fake overlay",
                       "boxes_png": b"fake boxes", "heatmap_png": b"fake heatmap"},
            "model": {"resolved_architecture": "test_model"},
            "n_candidates": 1,
            "foreground_pixels": 12,
            "threshold": 0.5,
            "min_area": 20,
            "candidates": [{"id": 1, "x": 1, "y": 2, "width": 3, "height": 4,
                             "pixel_area": 12, "mean_predicted_probability": 0.8}],
            "percentage_narrowing": None,
            "severity": None,
            "limitations": ["No clinical severity is reported."],
        }


def test_analyzer_cache_uses_checkpoint_content_hash(monkeypatch, tmp_path):
    created = []

    class Loaded:
        def __init__(self, path):
            self.content = path.read_bytes()
            created.append(self)

    checkpoint = tmp_path / "active.pth"
    checkpoint.write_bytes(b"weights-a")
    monkeypatch.setattr(analysis_api, "StenosisAnalyzer", Loaded)
    analysis_api._load_analyzer_cached.cache_clear()
    first = analysis_api._load_analyzer(str(checkpoint))
    checkpoint.write_bytes(b"weights-b")
    second = analysis_api._load_analyzer(str(checkpoint))
    assert first is not second
    assert [item.content for item in created] == [b"weights-a", b"weights-b"]
    analysis_api._load_analyzer_cached.cache_clear()


def test_experimental_vessel_threshold_requires_validation_only_report(monkeypatch, tmp_path):
    report_dir = tmp_path / "vessel_segmentation"
    report_dir.mkdir()
    monkeypatch.setattr(analysis_api, "reports_dir", lambda: tmp_path)
    checkpoint = tmp_path / "syntax_unet8_experiment.pth"
    with pytest.raises(ValueError, match="validation-selected threshold report"):
        analysis_api._experimental_vessel_threshold(checkpoint)
    report = report_dir / "syntax_unet8_experiment_syntax_validation.json"
    report.write_text('{"dataset_split":"syntax/val","test_split_used":false,"selected_threshold":0.75}', encoding="utf-8")
    assert analysis_api._experimental_vessel_threshold(checkpoint) == 0.75
    report.write_text('{"dataset_split":"syntax/test","test_split_used":false,"selected_threshold":0.75}', encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid validation-only report"):
        analysis_api._experimental_vessel_threshold(checkpoint)


def test_analysis_history_artifacts_and_exports(client, monkeypatch, tmp_path, png_bytes):
    checkpoint = tmp_path / "model.pth"
    checkpoint.touch()
    monkeypatch.setattr(analysis_api, "_model_path", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: FakeAnalyzer())
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: tmp_path)

    token, _ = register_and_login(client, "analysis@example.com")
    headers = auth_header(token)
    created = client.post("/api/cases", json={
        "case_identifier": "ANALYSIS-1", "patient_identifier": "SYNTH-1", "imaging_modality": "CTA",
    }, headers=headers)
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    uploaded = client.post(f"/api/cases/{case_id}/upload", files={"file": ("image.png", png_bytes, "image/png")}, headers=headers)
    assert uploaded.status_code == 200, uploaded.text

    response = client.post(f"/api/cases/{case_id}/analyze", headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["severity"] is None and data["percentage_narrowing"] is None
    measurement = data["diameter_measurement"]
    assert measurement["measurement_status"] == "unavailable"
    assert measurement["reference_vessel_diameter_mm"] is None
    assert measurement["minimum_lumen_diameter_mm"] is None
    assert measurement["reference_vessel_diameter_px"] is None
    assert measurement["minimum_lumen_diameter_px"] is None
    assert measurement["stenosis_percentage"] is None
    assert measurement["measurement_location"] is None
    assert "not vessel lumen boundaries" in measurement["reason"]
    # The fake candidate has a 3-pixel bbox width; it must never be reused as a lumen diameter.
    assert data["candidates"][0]["width"] == 3
    assert measurement["minimum_lumen_diameter_mm"] is None
    calibration = data["image_calibration"]
    assert calibration["status"] == "unavailable"
    assert calibration["row_spacing_mm_per_pixel"] is None
    assert calibration["used_for_measurement"] is False
    assert calibration["calibration_verified"] is False
    assert calibration["transform_verified"] is False
    assert "Raster image" in calibration["reason"]
    assert data["candidate_count"] == 1
    assert len(data["checkpoint_sha256"]) == 64
    assert client.get(data["artifacts"]["mask"], headers=headers).status_code == 200
    assert len(client.get(f"/api/cases/{case_id}/analyses", headers=headers).json()) == 1
    json_response = client.get(f"/api/cases/{case_id}/reports/json", headers=headers)
    assert json_response.status_code == 200
    exported_measurement = json_response.json()[0]["analysis"]["diameter_measurement"]
    assert exported_measurement == measurement
    assert json_response.json()[0]["analysis"]["image_calibration"] == calibration
    csv_response = client.get(f"/api/cases/{case_id}/reports/csv", headers=headers)
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "predicted_probability" in csv_response.text and ",1," in csv_response.text
    assert "reference_vessel_diameter_mm" in csv_response.text
    assert "minimum_lumen_diameter_mm" in csv_response.text
    assert "reference_vessel_diameter_px" in csv_response.text
    assert "minimum_lumen_diameter_px" in csv_response.text
    assert "measurement_status" in csv_response.text and "unavailable" in csv_response.text
    assert "pixel_spacing_status" in csv_response.text and "pixel_spacing_used_for_measurement" in csv_response.text
    pdf = client.get(f"/api/cases/{case_id}/reports/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-1.4")
    assert b"Candidate 1" in pdf.content and b"Unable to calculate" in pdf.content
    assert b"reference mm=unavailable" in pdf.content and b"minimum lumen mm=unavailable" in pdf.content
    assert b"Image calibration: unavailable" in pdf.content

    monkeypatch.setattr(analysis_api, "integrated_gradients_attribution", lambda *args, **kwargs: (
        np.ones((64, 64), dtype=np.float32), {"method": "integrated_gradients", "steps": 16,
        "interpretation": "Relative attribution, not clinical confidence."}
    ))
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: SimpleNamespace(
        model=object(), image_size=256, device="cpu", meta={"normalization": "none"}, threshold=0.5,
    ))
    explained = client.post(f"/api/analyses/{data['id']}/explain", headers=headers)
    assert explained.status_code == 200, explained.text
    assert explained.json()["explainability"]["method"] == "integrated_gradients"
    assert "integrated_gradients" in explained.json()["artifacts"]
    attribution = client.get(explained.json()["artifacts"]["integrated_gradients"], headers=headers)
    assert attribution.status_code == 200
    attributed_json = client.get(f"/api/cases/{case_id}/reports/json", headers=headers).json()
    assert attributed_json[0]["analysis"]["explainability"]["method"] == "integrated_gradients"
    attributed_csv = client.get(f"/api/cases/{case_id}/reports/csv", headers=headers)
    assert "explainability_method" in attributed_csv.text and "integrated_gradients" in attributed_csv.text
    attributed_pdf = client.get(f"/api/cases/{case_id}/reports/pdf", headers=headers)
    assert b"Input attribution: integrated_gradients" in attributed_pdf.content
    outsider_token, _ = register_and_login(client, "explanation-outsider@example.com")
    assert client.post(f"/api/analyses/{data['id']}/explain", headers=auth_header(outsider_token)).status_code == 404
    changed_checkpoint = tmp_path / "changed-model.pth"
    changed_checkpoint.write_bytes(b"different checkpoint")
    monkeypatch.setattr(analysis_api, "_model_path", lambda: changed_checkpoint)
    mismatch = client.post(f"/api/analyses/{data['id']}/explain", headers=headers)
    assert mismatch.status_code == 409 and "differs" in mismatch.json()["detail"]


def test_analysis_retains_reported_dicom_spacing_without_using_it_for_measurement(client, monkeypatch, tmp_path, png_bytes):
    checkpoint = tmp_path / "model.pth"
    checkpoint.touch()
    monkeypatch.setattr(analysis_api, "_model_path", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: FakeAnalyzer())
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: tmp_path)
    loaded = SimpleNamespace(
        array=np.zeros((64, 64), dtype=np.uint8), is_dicom=True,
        metadata={"pixel_spacing": [0.3, 0.25], "pixel_spacing_status": "reported_valid_values",
                  "pixel_spacing_calibration_type": "GEOMETRY"},
    )
    monkeypatch.setattr(analysis_api, "load_image", lambda _path: loaded)
    token, _ = register_and_login(client, "analysis-dicom-spacing@example.com")
    headers = auth_header(token)
    case = client.post("/api/cases", json={
        "case_identifier": "DICOM-SPACING", "patient_identifier": "SYNTH-DICOM", "imaging_modality": "XCA",
    }, headers=headers).json()
    uploaded = client.post(f"/api/cases/{case['id']}/upload", files={
        "file": ("image.png", png_bytes, "image/png"),
    }, headers=headers)
    assert uploaded.status_code == 200
    response = client.post(f"/api/cases/{case['id']}/analyze", headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["image_calibration"] == {
        "is_dicom": True,
        "status": "reported_valid_values", "source": "DICOM PixelSpacing",
        "pixel_spacing_status": "reported_valid_values",
        "pixel_spacing_row_column_mm": [0.3, 0.25],
        "row_spacing_mm_per_pixel": 0.3, "column_spacing_mm_per_pixel": 0.25,
        "calibration_type": "GEOMETRY", "used_for_measurement": False,
        "calibration_verified": False, "transform_verified": False,
        "reason": (
            "Positive DICOM PixelSpacing values are reported in row/column order. "
            "They are provenance only: angiographic calibration, magnification, and transform suitability "
            "have not been verified, so these values are not used for lumen measurements."
        ),
    }
    assert data["diameter_measurement"]["stenosis_percentage"] is None
    assert data["diameter_measurement"]["minimum_lumen_diameter_mm"] is None
    csv_report = client.get(f"/api/cases/{case['id']}/reports/csv", headers=headers)
    assert "0.3" in csv_report.text and "0.25" in csv_report.text
    pdf_report = client.get(f"/api/cases/{case['id']}/reports/pdf", headers=headers)
    assert b"DICOM PixelSpacing reported row/column mm per pixel: 0.3/0.25" in pdf_report.content


def test_experimental_vessel_region_mode_persists_widths_and_exports(client, monkeypatch, tmp_path, png_bytes):
    checkpoint = tmp_path / "syntax_unet8_experiment.pth"
    checkpoint.touch()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    monkeypatch.setattr(analysis_api, "_experimental_vessel_checkpoint", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: artifact_dir)
    monkeypatch.setattr(analysis_api, "_load_vessel_region_model", lambda _path: (object(), {
        "task": "syntax", "resolved_architecture": "unet", "image_size": 64, "normalization": "none",
    }))
    monkeypatch.setattr(analysis_api, "_experimental_vessel_threshold", lambda *_: 0.75)
    probability = np.zeros((64, 64), dtype=np.float32)
    probability[27:36, 4:60] = 0.95
    monkeypatch.setattr(analysis_api, "predict_image", lambda *_args, **_kwargs: probability)

    token, _ = register_and_login(client, "experimental-vessel@example.com")
    headers = auth_header(token)
    case = client.post("/api/cases", json={
        "case_identifier": "VESSEL-EXP-1", "patient_identifier": "SYNTH-V1", "imaging_modality": "XCA",
    }, headers=headers)
    assert case.status_code == 201, case.text
    case_id = case.json()["id"]
    upload = client.post(f"/api/cases/{case_id}/upload", files={
        "file": ("vessel.png", png_bytes, "image/png"),
    }, headers=headers)
    assert upload.status_code == 200, upload.text

    response = client.post(f"/api/cases/{case_id}/analyze?mode=vessel_region_experimental", headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["analysis_mode"] == "vessel_region_experimental"
    assert data["width_unit"] == "pixel"
    assert data["width_measurements"]
    assert 7 <= data["minimum_estimated_vessel_region_width_px"] <= 10
    assert data["percentage_narrowing"] is None and data["severity"] is None
    assert data["diameter_measurement"]["minimum_lumen_diameter_mm"] is None
    assert {"centerline", "cross_sections", "mask", "overlay", "heatmap"} <= set(data["artifacts"])
    assert all(client.get(url, headers=headers).status_code == 200 for url in data["artifacts"].values())
    outsider_token, _ = register_and_login(client, "experimental-vessel-outsider@example.com")
    assert client.get(data["artifacts"]["cross_sections"], headers=auth_header(outsider_token)).status_code == 404
    assert client.post(f"/api/cases/{case_id}/analyze?mode=vessel_region_experimental").status_code == 401
    history = client.get(f"/api/cases/{case_id}/analyses", headers=headers).json()
    assert history[0]["analysis_mode"] == "vessel_region_experimental"
    json_export = client.get(f"/api/cases/{case_id}/reports/json", headers=headers).json()[0]["analysis"]
    assert json_export["width_measurements"] == data["width_measurements"]
    csv_export = client.get(f"/api/cases/{case_id}/reports/csv", headers=headers)
    assert "analysis_mode" in csv_export.text
    assert "minimum_estimated_vessel_region_width_px" in csv_export.text
    pdf = client.get(f"/api/cases/{case_id}/reports/pdf", headers=headers)
    assert pdf.status_code == 200 and b"pixel estimates, not lumen diameters" in pdf.content
    assert b"Width section 1: 8.5 px at x=" in pdf.content


def test_validation_comparison_images_require_authentication(client):
    token, _ = register_and_login(client, "validation-viewer@example.com")
    headers = auth_header(token)
    examples = client.get("/api/models/validation/examples", headers=headers)
    assert examples.status_code == 200, examples.text
    assert examples.json()
    image = client.get(examples.json()[0]["image_url"], headers=headers)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert client.get("/api/models/validation/examples").status_code == 401


def test_generated_analysis_files_follow_owned_shared_assigned_permissions(
    client, db_session, monkeypatch, tmp_path, png_bytes
):
    checkpoint = tmp_path / "model.pth"
    checkpoint.touch()
    monkeypatch.setattr(analysis_api, "_model_path", lambda: checkpoint)
    monkeypatch.setattr(analysis_api, "_load_analyzer", lambda _path: FakeAnalyzer())
    analysis_dir = tmp_path / "analysis-artifacts"
    analysis_dir.mkdir()
    monkeypatch.setattr(analysis_api, "_analysis_dir", lambda: analysis_dir)

    owner_token, _ = register_and_login(client, "artifact-owner@example.com")
    shared_token, shared_user = register_and_login(client, "artifact-shared@example.com")
    outsider_token, _ = register_and_login(client, "artifact-outsider@example.com")
    admin = make_user(db_session, "artifact-admin@example.com", UserRole.ADMINISTRATOR.value)
    assigned = make_user(db_session, "artifact-assigned@example.com", UserRole.RADIOLOGIST.value)
    admin_login = client.post("/api/auth/login", json={"email": admin.email, "password": "Password123"})
    assigned_login = client.post("/api/auth/login", json={"email": assigned.email, "password": "Password123"})
    admin_token = admin_login.json()["access_token"]
    assigned_token = assigned_login.json()["access_token"]

    case = client.post(
        "/api/cases",
        json={"case_identifier": "ARTIFACT-ACCESS", "patient_identifier": "SYNTH-ART", "imaging_modality": "CTA"},
        headers=auth_header(owner_token),
    ).json()
    uploaded = client.post(
        f"/api/cases/{case['id']}/upload",
        files={"file": ("image.png", png_bytes, "image/png")},
        headers=auth_header(owner_token),
    )
    assert uploaded.status_code == 200, uploaded.text
    analyzed = client.post(f"/api/cases/{case['id']}/analyze", headers=auth_header(owner_token))
    assert analyzed.status_code == 201, analyzed.text
    analysis = analyzed.json()
    artifact_urls = analysis["artifacts"]
    assert set(artifact_urls) == {"mask", "overlay", "boxes", "heatmap"}

    for url in artifact_urls.values():
        assert client.get(url, headers=auth_header(owner_token)).status_code == 200
        assert client.get(url, headers=auth_header(outsider_token)).status_code == 404

    shared = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": shared_user["id"], "access_type": "shared"},
        headers=auth_header(owner_token),
    )
    assert shared.status_code == 201, shared.text
    assert client.get(artifact_urls["overlay"], headers=auth_header(shared_token)).status_code == 200
    assert client.get(f"/api/analyses/{analysis['id']}", headers=auth_header(shared_token)).status_code == 200

    assignment = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": assigned.id, "access_type": "assigned"},
        headers=auth_header(admin_token),
    )
    assert assignment.status_code == 201, assignment.text
    assert client.get(artifact_urls["heatmap"], headers=auth_header(assigned_token)).status_code == 200
    assert client.get(f"/api/cases/{case['id']}/reports/json", headers=auth_header(assigned_token)).status_code == 200

    assert client.get(f"/api/analyses/{analysis['id']}", headers=auth_header(outsider_token)).status_code == 404
    assert client.get(f"/api/cases/{case['id']}/reports/json", headers=auth_header(outsider_token)).status_code == 404

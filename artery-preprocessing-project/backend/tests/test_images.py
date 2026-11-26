import io

from tests.conftest import auth_header, register_and_login


def _ready_case(client, token):
    created = client.post(
        "/api/cases",
        json={
            "case_identifier": "IMG-001",
            "patient_identifier": "SYNTH-200",
            "imaging_modality": "CTA",
            "anatomical_region": "coronary",
        },
        headers=auth_header(token),
    )
    return created.json()["id"]


def test_valid_image_upload_and_preprocess(client, png_bytes, storage_dirs):
    token, _ = register_and_login(client, "img@example.com")
    case_id = _ready_case(client, token)
    upload = client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("vessel.png", png_bytes, "image/png")},
        headers=auth_header(token),
    )
    assert upload.status_code == 200, upload.text
    original = storage_dirs["upload"] / next(storage_dirs["upload"].iterdir())
    original_bytes = original.read_bytes()
    preprocess = client.post(
        f"/api/cases/{case_id}/preprocess",
        json={
            "normalize": True,
            "normalize_method": "minmax",
            "resize": True,
            "target_width": 48,
            "target_height": 48,
            "preserve_aspect_ratio": True,
            "denoise": True,
            "denoise_method": "gaussian",
            "contrast": True,
            "contrast_method": "clahe",
        },
        headers=auth_header(token),
    )
    assert preprocess.status_code == 200, preprocess.text
    body = preprocess.json()
    assert body["status"] == "completed"
    assert body["processed_width"] is not None
    assert original.read_bytes() == original_bytes
    history = client.get(f"/api/cases/{case_id}/preprocessing-history", headers=auth_header(token))
    assert history.status_code == 200
    assert len(history.json()) == 1
    image = client.get(f"/api/cases/{case_id}/image", headers=auth_header(token))
    assert image.status_code == 200
    processed = client.get(
        f"/api/cases/{case_id}/processed-image/{body['id']}",
        headers=auth_header(token),
    )
    assert processed.status_code == 200


def test_unsupported_image_rejected(client):
    token, _ = register_and_login(client, "badfmt@example.com")
    case_id = _ready_case(client, token)
    res = client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth_header(token),
    )
    assert res.status_code == 400


def test_corrupted_image_rejected(client):
    token, _ = register_and_login(client, "corrupt@example.com")
    case_id = _ready_case(client, token)
    res = client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("bad.png", b"\x89PNG\r\nnotanimage", "image/png")},
        headers=auth_header(token),
    )
    assert res.status_code == 400


def test_oversized_file_rejected(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100")
    get_settings.cache_clear()
    token, _ = register_and_login(client, "big@example.com")
    case_id = _ready_case(client, token)
    payload = b"0" * 200
    res = client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("big.png", payload, "image/png")},
        headers=auth_header(token),
    )
    assert res.status_code in {400, 413}
    get_settings.cache_clear()


def test_invalid_preprocessing_parameters(client, png_bytes):
    token, _ = register_and_login(client, "params@example.com")
    case_id = _ready_case(client, token)
    client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": ("vessel.png", png_bytes, "image/png")},
        headers=auth_header(token),
    )
    res = client.post(
        f"/api/cases/{case_id}/preprocess",
        json={"target_width": 1, "resize": True},
        headers=auth_header(token),
    )
    assert res.status_code == 422

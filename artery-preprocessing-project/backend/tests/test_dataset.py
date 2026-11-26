import json

from PIL import Image

from app.core.permissions import UserRole
from tests.conftest import auth_header, make_user
from tests.test_cases import _create_case


def _login(client, email, password="Password123"):
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _upload(client, token, case_id, filename, payload, content_type="image/png"):
    return client.post(
        f"/api/cases/{case_id}/upload",
        files={"file": (filename, payload, content_type)},
        headers=auth_header(token),
    )


def _write_png(path, color=80):
    Image.new("L", (64, 64), color=color).save(path)


def test_empty_sample_directory_has_clear_message(client, db_session, storage_dirs):
    scientist = make_user(db_session, "ds-empty@example.com", UserRole.DATA_SCIENTIST.value)
    token = _login(client, scientist.email)
    summary = client.get("/api/dataset/summary", headers=auth_header(token))
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["exists"] is True
    assert body["sample_supported_count"] == 0
    assert body["uploaded_supported_count"] == 0
    assert body["supported_count"] == 0
    assert body["formats"] == {}
    assert body["sample"]["formats"] == {}
    assert "No sample images found" in body["sample"]["note"]
    assert "No sample images found" in body["note"]
    assert "uploaded" in body["note"].lower()
    assert body["arcade"]["exists"] is True
    assert body["arcade"]["tasks"]["stenosis"]["test"]["annotation_status"] == "not_inspected"
    assert body["arcade"]["tasks"]["stenosis"]["test"]["selection_eligible"] is False


def test_arcade_summary_reports_train_validation_and_keeps_test_annotations_unread(client, db_session, storage_dirs):
    scientist = make_user(db_session, "ds-arcade@example.com", UserRole.DATA_SCIENTIST.value)
    token = _login(client, scientist.email)
    root = storage_dirs["arcade"]

    for task in ("stenosis", "syntax"):
        for split in ("train", "val", "test"):
            (root / task / split / "images").mkdir(parents=True)
            (root / task / split / "annotations").mkdir(parents=True)
            (root / task / split / "images" / "sample.png").write_bytes(b"")

    (root / "stenosis" / "train" / "annotations" / "train.json").write_text(json.dumps({
        "images": [{"id": 1}, {"id": 2}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 26},
            {"id": 2, "image_id": 2, "category_id": 1},
        ],
    }), encoding="utf-8")
    (root / "stenosis" / "val" / "annotations" / "val.json").write_text(json.dumps({
        "images": [{"id": 3}], "annotations": [{"id": 3, "image_id": 3, "category_id": 26}],
    }), encoding="utf-8")
    (root / "syntax" / "train" / "annotations" / "train.json").write_text(json.dumps({
        "images": [{"id": 1}], "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1},
            {"id": 2, "image_id": 1, "category_id": 26},
        ],
    }), encoding="utf-8")
    (root / "syntax" / "val" / "annotations" / "val.json").write_text(json.dumps({
        "images": [], "annotations": [],
    }), encoding="utf-8")
    holdout_annotation = root / "stenosis" / "test" / "annotations" / "test.json"
    holdout_annotation.write_text("intentionally malformed and must not be read", encoding="utf-8")

    response = client.get("/api/dataset/summary", headers=auth_header(token))
    assert response.status_code == 200, response.text
    arcade = response.json()["arcade"]
    assert arcade["root"] == str(root)
    assert arcade["exists"] is True
    assert arcade["tasks"]["stenosis"]["train"]["image_count"] == 1
    assert arcade["tasks"]["stenosis"]["train"]["annotation_image_count"] == 2
    assert arcade["tasks"]["stenosis"]["train"]["annotation_count"] == 1
    assert arcade["tasks"]["stenosis"]["train"]["category_ids"] == [26]
    assert arcade["tasks"]["syntax"]["train"]["annotation_count"] == 1
    assert arcade["tasks"]["syntax"]["train"]["category_ids"] == [1]
    assert arcade["tasks"]["stenosis"]["val"]["selection_eligible"] is True
    assert arcade["tasks"]["stenosis"]["test"]["annotation_status"] == "not_inspected"
    assert arcade["tasks"]["stenosis"]["test"]["annotation_count"] is None


def test_dataset_counts_sample_and_uploaded_separately(client, db_session, storage_dirs, png_bytes):
    scientist = make_user(db_session, "ds-count@example.com", UserRole.DATA_SCIENTIST.value)
    token = _login(client, scientist.email)
    sample_png = storage_dirs["dataset"] / "public.png"
    _write_png(sample_png)
    sample_jpeg = storage_dirs["dataset"] / "public.jpg"
    Image.new("L", (64, 64), color=40).save(sample_jpeg, format="JPEG")
    (storage_dirs["dataset"] / "notes.txt").write_text("ignore me")
    (storage_dirs["processed"] / "processed.png").write_bytes(png_bytes)

    case = _create_case(client, token, "DS-IMG-1").json()
    upload = _upload(client, token, case["id"], "vessel.png", png_bytes)
    assert upload.status_code == 200, upload.text

    summary = client.get("/api/dataset/summary", headers=auth_header(token)).json()
    assert summary["sample_supported_count"] == 2
    assert summary["uploaded_supported_count"] == 1
    assert summary["supported_count"] == 3
    assert summary["sample"]["formats"]["PNG"] == 1
    assert summary["sample"]["formats"]["JPEG"] == 1
    assert summary["uploaded"]["formats"]["PNG"] == 1
    assert summary["formats"]["PNG"] == 2
    assert summary["formats"]["JPEG"] == 1
    assert summary["unreadable_count"] == 0


def test_unreadable_sample_files_are_counted(client, db_session, storage_dirs):
    scientist = make_user(db_session, "ds-unread@example.com", UserRole.DATA_SCIENTIST.value)
    token = _login(client, scientist.email)
    _write_png(storage_dirs["dataset"] / "ok.png")
    (storage_dirs["dataset"] / "bad.png").write_bytes(b"\x89PNG\r\nnotanimage")
    summary = client.get("/api/dataset/summary", headers=auth_header(token)).json()
    assert summary["sample_supported_count"] == 1
    assert summary["sample"]["unreadable_count"] == 1
    assert summary["unreadable_count"] == 1


def test_missing_uploaded_file_is_not_counted(client, db_session, storage_dirs, png_bytes):
    scientist = make_user(db_session, "ds-missing@example.com", UserRole.DATA_SCIENTIST.value)
    token = _login(client, scientist.email)
    case = _create_case(client, token, "DS-MISS").json()
    upload = _upload(client, token, case["id"], "gone.png", png_bytes)
    assert upload.status_code == 200, upload.text
    stored = next(storage_dirs["upload"].iterdir())
    stored.unlink()
    summary = client.get("/api/dataset/summary", headers=auth_header(token)).json()
    assert summary["uploaded_supported_count"] == 0
    assert summary["uploaded"]["unreadable_count"] == 0


def test_data_scientist_does_not_see_private_case_images(client, db_session, storage_dirs, png_bytes):
    scientist = make_user(db_session, "ds-scope@example.com", UserRole.DATA_SCIENTIST.value)
    owner = make_user(db_session, "ds-private-owner@example.com", UserRole.RESEARCHER.value)
    token_ds = _login(client, scientist.email)
    token_owner = _login(client, owner.email)
    own = _create_case(client, token_ds, "DS-VISIBLE").json()
    hidden = _create_case(client, token_owner, "DS-PRIVATE").json()
    assert _upload(client, token_ds, own["id"], "own.png", png_bytes).status_code == 200
    assert _upload(client, token_owner, hidden["id"], "hidden.png", png_bytes).status_code == 200

    summary = client.get("/api/dataset/summary", headers=auth_header(token_ds)).json()
    assert summary["uploaded_supported_count"] == 1
    assert summary["uploaded"]["formats"] == {"PNG": 1}

    shared = client.post(
        f"/api/cases/{hidden['id']}/access",
        json={"user_id": scientist.id, "access_type": "shared"},
        headers=auth_header(token_owner),
    )
    assert shared.status_code == 201, shared.text
    after = client.get("/api/dataset/summary", headers=auth_header(token_ds)).json()
    assert after["uploaded_supported_count"] == 2


def test_admin_dataset_counts_all_uploaded_images(client, db_session, storage_dirs, png_bytes):
    admin = make_user(db_session, "admin-dataset@example.com", UserRole.ADMINISTRATOR.value)
    owner = make_user(db_session, "admin-ds-owner@example.com", UserRole.RESEARCHER.value)
    token_admin = _login(client, admin.email)
    token_owner = _login(client, owner.email)
    case = _create_case(client, token_owner, "ADM-DS").json()
    assert _upload(client, token_owner, case["id"], "admin.png", png_bytes).status_code == 200
    summary = client.get("/api/dataset/summary", headers=auth_header(token_admin)).json()
    assert summary["uploaded_supported_count"] == 1


def test_researcher_cannot_inspect_dataset(client, db_session):
    researcher = make_user(db_session, "research-dataset@example.com", UserRole.RESEARCHER.value)
    token = _login(client, researcher.email)
    assert client.get("/api/dataset/summary", headers=auth_header(token)).status_code == 403

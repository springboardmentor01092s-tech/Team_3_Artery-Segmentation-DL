from app.core.permissions import Permission, UserRole, has_permission
from tests.conftest import auth_header, make_user, register_and_login
from tests.test_cases import _create_case


def _login(client, email, password="Password123"):
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_researcher_sees_own_cases_only(client):
    token_a, user_a = register_and_login(client, "owner@example.com")
    token_b, _ = register_and_login(client, "other@example.com")
    created = _create_case(client, token_a, "OWN-001")
    _create_case(client, token_b, "PRIV-002")
    listed = client.get("/api/cases", headers=auth_header(token_a))
    assert listed.status_code == 200
    identifiers = [item["case_identifier"] for item in listed.json()]
    assert identifiers == ["OWN-001"]
    assert created.json()["current_access"] == "owner"
    assert user_a["role"] == UserRole.RESEARCHER.value
    assert user_a["permissions"]


def test_researcher_cannot_see_private_case_in_list_or_detail(client):
    token_a, _ = register_and_login(client, "a-vis@example.com")
    token_b, _ = register_and_login(client, "b-vis@example.com")
    created = _create_case(client, token_a, "HIDDEN-1")
    case_id = created.json()["id"]
    listed = client.get("/api/cases", headers=auth_header(token_b))
    assert all(item["id"] != case_id for item in listed.json())
    assert client.get(f"/api/cases/{case_id}", headers=auth_header(token_b)).status_code == 404
    assert client.patch(f"/api/cases/{case_id}", json={"clinical_notes": "no"}, headers=auth_header(token_b)).status_code == 404
    assert client.delete(f"/api/cases/{case_id}", headers=auth_header(token_b)).status_code == 404


def test_shared_case_is_visible_and_revoke_removes_access(client):
    token_owner, owner = register_and_login(client, "share-owner@example.com")
    token_peer, peer = register_and_login(client, "share-peer@example.com")
    case = _create_case(client, token_owner, "SHARE-1").json()
    grant = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": peer["id"], "access_type": "shared"},
        headers=auth_header(token_owner),
    )
    assert grant.status_code == 201, grant.text
    listed = client.get("/api/cases", headers=auth_header(token_peer))
    assert [item["id"] for item in listed.json()] == [case["id"]]
    fetched = client.get(f"/api/cases/{case['id']}", headers=auth_header(token_peer))
    assert fetched.status_code == 200
    assert fetched.json()["current_access"] == "shared"
    notes = client.patch(
        f"/api/cases/{case['id']}",
        json={"clinical_notes": "peer should not mutate ownership metadata"},
        headers=auth_header(token_peer),
    )
    assert notes.status_code == 403
    revoked = client.delete(
        f"/api/cases/{case['id']}/access/{grant.json()['id']}",
        headers=auth_header(token_owner),
    )
    assert revoked.status_code == 204
    assert client.get(f"/api/cases/{case['id']}", headers=auth_header(token_peer)).status_code == 404
    assert client.get("/api/cases", headers=auth_header(token_peer)).json() == []


def test_radiologist_follows_visibility_without_admin_permissions(client, db_session):
    owner = make_user(db_session, "radio-owner@example.com", UserRole.RADIOLOGIST.value)
    peer = make_user(db_session, "radio-peer@example.com", UserRole.RADIOLOGIST.value)
    outsider = make_user(db_session, "radio-out@example.com", UserRole.RADIOLOGIST.value)
    token_owner = _login(client, owner.email)
    token_peer = _login(client, peer.email)
    token_out = _login(client, outsider.email)
    assert has_permission(UserRole.RADIOLOGIST, Permission.CASE_SHARE)
    assert not has_permission(UserRole.RADIOLOGIST, Permission.CASE_ASSIGN)
    assert not has_permission(UserRole.RADIOLOGIST, Permission.USER_MANAGE)
    case = _create_case(client, token_owner, "RAD-1").json()
    assigned = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": peer.id, "access_type": "assigned"},
        headers=auth_header(token_owner),
    )
    assert assigned.status_code == 403
    shared = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": peer.id, "access_type": "shared"},
        headers=auth_header(token_owner),
    )
    assert shared.status_code == 201, shared.text
    assert client.get(f"/api/cases/{case['id']}", headers=auth_header(token_peer)).status_code == 200
    assert client.get(f"/api/cases/{case['id']}", headers=auth_header(token_out)).status_code == 404
    assert client.get("/api/admin/users", headers=auth_header(token_owner)).status_code == 403


def test_data_scientist_visibility_and_dataset_inspect(client, db_session):
    scientist = make_user(db_session, "ds@example.com", UserRole.DATA_SCIENTIST.value)
    other = make_user(db_session, "ds-other@example.com", UserRole.RESEARCHER.value)
    token_ds = _login(client, scientist.email)
    token_other = _login(client, other.email)
    own = _create_case(client, token_ds, "DS-OWN").json()
    hidden = _create_case(client, token_other, "DS-HIDDEN").json()
    listed = client.get("/api/cases", headers=auth_header(token_ds)).json()
    assert [item["id"] for item in listed] == [own["id"]]
    assert client.get(f"/api/cases/{hidden['id']}", headers=auth_header(token_ds)).status_code == 404
    summary = client.get("/api/dataset/summary", headers=auth_header(token_ds))
    assert summary.status_code == 200
    body = summary.json()
    assert body["sample_supported_count"] == 0
    assert body["uploaded_supported_count"] == 0
    assert "No sample images found" in body["sample"]["note"]
    researcher_token, _ = register_and_login(client, "no-dataset@example.com")
    assert client.get("/api/dataset/summary", headers=auth_header(researcher_token)).status_code == 403


def test_admin_sees_all_cases_and_can_assign(client, db_session):
    admin = make_user(db_session, "admin-access@example.com", UserRole.ADMINISTRATOR.value)
    owner = make_user(db_session, "owned@example.com", UserRole.RESEARCHER.value)
    assignee = make_user(db_session, "assignee@example.com", UserRole.RADIOLOGIST.value)
    token_admin = _login(client, admin.email)
    token_owner = _login(client, owner.email)
    token_assignee = _login(client, assignee.email)
    case = _create_case(client, token_owner, "ADM-ALL").json()
    listed = client.get("/api/cases", headers=auth_header(token_admin)).json()
    assert any(item["id"] == case["id"] for item in listed)
    grant = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": assignee.id, "access_type": "assigned"},
        headers=auth_header(token_admin),
    )
    assert grant.status_code == 201, grant.text
    fetched = client.get(f"/api/cases/{case['id']}", headers=auth_header(token_assignee))
    assert fetched.status_code == 200
    assert fetched.json()["current_access"] == "assigned"


def test_inaccessible_images_and_preprocessing_are_blocked(client, png_bytes):
    token_a, _ = register_and_login(client, "img-owner@example.com")
    token_b, user_b = register_and_login(client, "img-other@example.com")
    case = _create_case(client, token_a, "IMG-PRIV").json()
    upload = client.post(
        f"/api/cases/{case['id']}/upload",
        files={"file": ("vessel.png", png_bytes, "image/png")},
        headers=auth_header(token_a),
    )
    assert upload.status_code == 200, upload.text
    preprocess = client.post(
        f"/api/cases/{case['id']}/preprocess",
        json={"normalize": True, "normalize_method": "minmax"},
        headers=auth_header(token_a),
    )
    assert preprocess.status_code == 200, preprocess.text
    run_id = preprocess.json()["id"]
    headers_b = auth_header(token_b)
    assert client.post(
        f"/api/cases/{case['id']}/upload",
        files={"file": ("other.png", png_bytes, "image/png")},
        headers=headers_b,
    ).status_code == 404
    assert client.post(
        f"/api/cases/{case['id']}/preprocess",
        json={"normalize": True, "normalize_method": "minmax"},
        headers=headers_b,
    ).status_code == 404
    assert client.get(f"/api/cases/{case['id']}/image", headers=headers_b).status_code == 404
    assert client.get(f"/api/cases/{case['id']}/preprocessing-history", headers=headers_b).status_code == 404
    assert client.get(f"/api/cases/{case['id']}/processed-image/{run_id}", headers=headers_b).status_code == 404

    shared = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": user_b["id"], "access_type": "shared"},
        headers=auth_header(token_a),
    )
    assert shared.status_code == 201
    assert client.get(f"/api/cases/{case['id']}/image", headers=headers_b).status_code == 200
    assert client.get(f"/api/cases/{case['id']}/preprocessing-history", headers=headers_b).status_code == 200
    assert client.get(f"/api/cases/{case['id']}/processed-image/{run_id}", headers=headers_b).status_code == 200


def test_cannot_gain_access_by_swapping_ids(client, png_bytes):
    token_a, _ = register_and_login(client, "swap-a@example.com")
    token_b, _ = register_and_login(client, "swap-b@example.com")
    case_a = _create_case(client, token_a, "SWAP-A").json()
    case_b = _create_case(client, token_b, "SWAP-B").json()
    client.post(
        f"/api/cases/{case_a['id']}/upload",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=auth_header(token_a),
    )
    run_a = client.post(
        f"/api/cases/{case_a['id']}/preprocess",
        json={"normalize": True, "normalize_method": "minmax"},
        headers=auth_header(token_a),
    ).json()["id"]
    client.post(
        f"/api/cases/{case_b['id']}/upload",
        files={"file": ("b.png", png_bytes, "image/png")},
        headers=auth_header(token_b),
    )
    missing = "00000000-0000-4000-8000-000000000000"
    assert client.get(f"/api/cases/{missing}", headers=auth_header(token_b)).status_code == 404
    assert client.get(
        f"/api/cases/{case_b['id']}/processed-image/{run_a}",
        headers=auth_header(token_b),
    ).status_code == 404
    assert client.get(
        f"/api/cases/{case_a['id']}/processed-image/{run_a}",
        headers=auth_header(token_b),
    ).status_code == 404


def test_dashboard_counts_match_visible_cases(client, db_session):
    token_a, _ = register_and_login(client, "dash-a@example.com")
    token_b, user_b = register_and_login(client, "dash-b@example.com")
    case_a = _create_case(client, token_a, "DASH-A").json()
    _create_case(client, token_b, "DASH-B")
    stats_a = client.get("/api/dashboard/stats", headers=auth_header(token_a)).json()
    stats_b = client.get("/api/dashboard/stats", headers=auth_header(token_b)).json()
    assert stats_a["case_count"] == 1
    assert stats_b["case_count"] == 1
    grant = client.post(
        f"/api/cases/{case_a['id']}/access",
        json={"user_id": user_b["id"], "access_type": "shared"},
        headers=auth_header(token_a),
    )
    assert grant.status_code == 201
    stats_b_after = client.get("/api/dashboard/stats", headers=auth_header(token_b)).json()
    assert stats_b_after["case_count"] == 2
    assert stats_a["user_count"] is None
    admin = make_user(db_session, "dashboard-admin@example.com", UserRole.ADMINISTRATOR.value)
    token_admin = _login(client, admin.email)
    admin_stats = client.get("/api/dashboard/stats", headers=auth_header(token_admin)).json()
    assert admin_stats["case_count"] == 2
    assert admin_stats["user_count"] == 3


def test_dashboard_activity_counts_follow_case_visibility(client, png_bytes):
    owner_token, _ = register_and_login(client, "stats-owner@example.com")
    other_token, other = register_and_login(client, "stats-other@example.com")
    owner_case = _create_case(client, owner_token, "STATS-OWN").json()
    other_case = _create_case(client, other_token, "STATS-OTHER").json()

    for token, case_id in [(owner_token, owner_case["id"]), (other_token, other_case["id"])]:
        uploaded = client.post(
            f"/api/cases/{case_id}/upload", files={"file": ("image.png", png_bytes, "image/png")},
            headers=auth_header(token),
        )
        assert uploaded.status_code == 200
    processed = client.post(
        f"/api/cases/{owner_case['id']}/preprocess",
        json={"normalize": True, "normalize_method": "minmax"}, headers=auth_header(owner_token),
    )
    assert processed.status_code == 200

    own_stats = client.get("/api/dashboard/stats", headers=auth_header(other_token)).json()
    assert own_stats["case_count"] == 1
    assert own_stats["image_count"] == 1
    assert own_stats["preprocessing_count"] == 0
    assert own_stats["processed_case_count"] == 0
    assert own_stats["pending_case_count"] == 1

    shared = client.post(
        f"/api/cases/{owner_case['id']}/access",
        json={"user_id": other["id"], "access_type": "shared"}, headers=auth_header(owner_token),
    )
    assert shared.status_code == 201
    shared_stats = client.get("/api/dashboard/stats", headers=auth_header(other_token)).json()
    assert shared_stats["case_count"] == 2
    assert shared_stats["image_count"] == 2
    assert shared_stats["preprocessing_count"] == 1
    assert shared_stats["processed_case_count"] == 1
    assert shared_stats["pending_case_count"] == 1


def test_self_grant_and_inactive_target_rejected(client, db_session):
    token, user = register_and_login(client, "self-grant@example.com")
    case = _create_case(client, token, "SELF-1").json()
    denied = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": user["id"], "access_type": "shared"},
        headers=auth_header(token),
    )
    assert denied.status_code == 400
    inactive = make_user(db_session, "inactive@example.com", UserRole.RESEARCHER.value)
    inactive.is_active = False
    db_session.commit()
    missing = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": inactive.id, "access_type": "shared"},
        headers=auth_header(token),
    )
    assert missing.status_code == 404
    duplicate = client.post(
        f"/api/cases/{case['id']}/access",
        json={"user_id": user["id"], "access_type": "shared"},
        headers=auth_header(token),
    )
    assert duplicate.status_code == 400

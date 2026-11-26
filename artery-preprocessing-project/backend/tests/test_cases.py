from app.core.permissions import UserRole
from tests.conftest import auth_header, make_user, register_and_login


def _create_case(client, token, identifier="CASE-001"):
    return client.post(
        "/api/cases",
        json={
            "case_identifier": identifier,
            "patient_identifier": "SYNTH-100",
            "age": 60,
            "gender": "unspecified",
            "medical_history": "Synthetic history",
            "risk_factors": "none listed",
            "clinical_notes": "Demo notes",
            "imaging_modality": "CTA",
            "anatomical_region": "coronary",
        },
        headers=auth_header(token),
    )


def test_case_create_and_retrieve(client):
    token, _ = register_and_login(client, "owner@example.com")
    created = _create_case(client, token)
    assert created.status_code == 201
    case_id = created.json()["id"]
    fetched = client.get(f"/api/cases/{case_id}", headers=auth_header(token))
    assert fetched.status_code == 200
    assert fetched.json()["case_identifier"] == "CASE-001"


def test_case_metadata_validation(client):
    token, _ = register_and_login(client, "invalid@example.com")
    res = client.post(
        "/api/cases",
        json={"case_identifier": "bad id", "patient_identifier": "x", "imaging_modality": "CTA"},
        headers=auth_header(token),
    )
    assert res.status_code == 422


def test_unauthorized_case_access(client):
    token_a, _ = register_and_login(client, "a@example.com")
    token_b, _ = register_and_login(client, "b@example.com")
    created = _create_case(client, token_a, "CASE-PRIV")
    case_id = created.json()["id"]
    res = client.get(f"/api/cases/{case_id}", headers=auth_header(token_b))
    assert res.status_code == 404


def test_search_cases(client):
    token, _ = register_and_login(client, "search@example.com")
    _create_case(client, token, "FIND-ME")
    _create_case(client, token, "OTHER-1")
    res = client.get("/api/cases", params={"search": "FIND"}, headers=auth_header(token))
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["case_identifier"] == "FIND-ME"


def test_admin_user_management(client, db_session):
    admin = make_user(db_session, "admin@example.com", UserRole.ADMINISTRATOR.value)
    login = client.post("/api/auth/login", json={"email": admin.email, "password": "Password123"})
    token = login.json()["access_token"]
    users = client.get("/api/admin/users", headers=auth_header(token))
    assert users.status_code == 200
    target, _ = register_and_login(client, "promote@example.com")
    me = client.get("/api/auth/me", headers=auth_header(target)).json()
    updated = client.patch(
        f"/api/admin/users/{me['id']}",
        json={"role": "radiologist", "is_active": True},
        headers=auth_header(token),
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "radiologist"
    logs = client.get("/api/admin/audit-logs", headers=auth_header(token))
    assert logs.status_code == 200
    assert len(logs.json()) >= 1


def test_admin_operations_validate_roles_activation_and_audit_limits(client, db_session):
    admin = make_user(db_session, "ops-admin@example.com", UserRole.ADMINISTRATOR.value)
    admin_token = client.post(
        "/api/auth/login", json={"email": admin.email, "password": "Password123"}
    ).json()["access_token"]
    regular_token, regular = register_and_login(client, "ops-target@example.com")
    admin_headers = auth_header(admin_token)
    regular_headers = auth_header(regular_token)

    assert client.get("/api/admin/users", headers=regular_headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=regular_headers).status_code == 403
    assert client.patch(
        f"/api/admin/users/{regular['id']}", json={"role": "root"}, headers=admin_headers
    ).status_code == 422
    assert client.patch(
        "/api/admin/users/missing-user", json={"is_active": False}, headers=admin_headers
    ).status_code == 404
    assert client.patch(
        f"/api/admin/users/{admin.id}", json={"is_active": False}, headers=admin_headers
    ).status_code == 400
    demote_last_admin = client.patch(
        f"/api/admin/users/{admin.id}", json={"role": "researcher"}, headers=admin_headers
    )
    assert demote_last_admin.status_code == 400
    assert "last active administrator" in demote_last_admin.json()["detail"].lower()
    assert client.get("/api/admin/users", headers=admin_headers).status_code == 200

    deactivated = client.patch(
        f"/api/admin/users/{regular['id']}", json={"is_active": False}, headers=admin_headers
    )
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    assert client.post(
        "/api/auth/login", json={"email": "ops-target@example.com", "password": "Password123"}
    ).status_code == 403
    assert client.get("/api/admin/audit-logs?limit=0", headers=admin_headers).status_code == 422
    assert client.get("/api/admin/audit-logs?limit=501", headers=admin_headers).status_code == 422

    reactivated = client.patch(
        f"/api/admin/users/{regular['id']}", json={"is_active": True, "role": "radiologist"}, headers=admin_headers
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["role"] == "radiologist" and reactivated.json()["is_active"] is True
    assert client.post(
        "/api/auth/login", json={"email": "ops-target@example.com", "password": "Password123"}
    ).status_code == 200
    assert client.get("/api/admin/audit-logs", headers=admin_headers).status_code == 200

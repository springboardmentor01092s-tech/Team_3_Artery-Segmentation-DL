from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.permissions import DEFAULT_REGISTRATION_ROLE
from app.security.passwords import hash_password, verify_password
from tests.conftest import auth_header, register_and_login


def test_password_hashing_is_not_plaintext():
    hashed = hash_password("Password123")
    assert hashed != "Password123"
    assert verify_password("Password123", hashed)
    assert not verify_password("wrong", hashed)


def test_register_and_login(client):
    token, user = register_and_login(client, "user@example.com")
    assert user["role"] == DEFAULT_REGISTRATION_ROLE.value
    assert user["role"] != "administrator"
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_invalid_credentials(client):
    register_and_login(client, "user2@example.com")
    res = client.post("/api/auth/login", json={"email": "user2@example.com", "password": "bad-password"})
    assert res.status_code == 401


def test_protected_route_requires_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_invalid_jwt(client):
    res = client.get("/api/auth/me", headers=auth_header("not-a-token"))
    assert res.status_code == 401


def test_expired_jwt(client):
    token, user = register_and_login(client, "expire@example.com")
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": user["id"],
            "role": user["role"],
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    res = client.get("/api/auth/me", headers=auth_header(expired))
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_profile_update(client):
    token, _ = register_and_login(client, "profile@example.com")
    res = client.patch("/api/auth/me", json={"full_name": "Updated Name"}, headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Name"


def test_non_admin_cannot_list_users(client):
    token, _ = register_and_login(client, "regular@example.com")
    res = client.get("/api/admin/users", headers=auth_header(token))
    assert res.status_code == 403

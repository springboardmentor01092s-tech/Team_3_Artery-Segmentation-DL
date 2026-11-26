from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import main
from app.core.deps import get_db


def test_health_reports_successful_database_readiness(client, db_session):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["database"] == "ok"
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


def test_health_reports_degraded_when_database_probe_fails(client):
    class UnavailableDatabase:
        def execute(self, _statement):
            raise OperationalError("SELECT 1", {}, RuntimeError("offline"))

    def broken_db():
        yield UnavailableDatabase()

    client.app.dependency_overrides[get_db] = broken_db
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "service": main.settings.app_name,
        "checks": {"database": "unavailable"},
    }


def test_request_telemetry_logs_route_template_without_query_values(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main.logger, "info", lambda *args: calls.append(args))

    response = client.get("/api/health?token=must-not-be-logged")

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == "HTTP request completed method=%s route=%s status=%s duration_ms=%.1f"
    assert "/api/health" in calls[0]
    assert "must-not-be-logged" not in str(calls)

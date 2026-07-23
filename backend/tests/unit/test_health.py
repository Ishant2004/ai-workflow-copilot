"""Health / probe endpoint tests."""

import pytest

pytestmark = pytest.mark.unit


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
    # request-id middleware echoes a correlation id
    assert resp.headers.get("X-Request-ID")


def test_liveness(client):
    assert client.get("/health/live").json() == {"status": "alive"}


def test_readiness_ready_when_no_deps_configured(client):
    """With no datastores configured, the service is trivially ready."""
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {}


def test_readiness_returns_503_when_dep_down(client, monkeypatch):
    """A configured-but-unreachable dependency makes readiness fail with 503."""
    import app.api.routes.health as health_module

    async def fake_checks(**_kwargs):
        return False, {"postgres": "error: connection refused"}

    monkeypatch.setattr(health_module, "run_readiness_checks", fake_checks)

    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"


def test_incoming_request_id_is_preserved(client):
    resp = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"

"""Smoke tests for the app skeleton."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
    # request-id middleware echoes a correlation id
    assert resp.headers.get("X-Request-ID")


def test_liveness_and_readiness():
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["docs"] == "/docs"

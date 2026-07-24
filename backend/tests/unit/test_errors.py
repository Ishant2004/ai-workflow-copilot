"""Consistent error-handling tests."""

import pytest
from app.config import Settings
from app.dependencies import get_planner_dep
from app.main import create_app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


class _BoomPlanner:
    async def plan(self, task_description: str):
        raise RuntimeError("secret internal detail")


def test_unhandled_exception_returns_safe_500():
    app = create_app(Settings(app_env="development", llm_provider="fake"))
    app.dependency_overrides[get_planner_dep] = lambda: _BoomPlanner()
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post("/api/planner/preview", json={"task_description": "x"})

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    # internals never leak to the client
    assert "secret internal detail" not in resp.text


def test_http_exception_shape_is_unchanged(workflow_client):
    # 404 still uses FastAPI's {"detail": ...} shape (frontend relies on it).
    import uuid

    resp = workflow_client.get(f"/api/workflows/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert "detail" in resp.json()

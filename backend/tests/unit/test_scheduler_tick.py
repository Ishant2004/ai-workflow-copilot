"""Worker-free scheduler tick endpoint tests (offline, in-memory repos)."""

import pytest
from app.config import Settings
from app.dependencies import get_document_repo, get_feedback_repo, get_workflow_repo
from app.main import create_app
from fastapi.testclient import TestClient

from tests.fakes import (
    InMemoryDocumentRepository,
    InMemoryFeedbackRepository,
    InMemoryWorkflowRepository,
)

pytestmark = pytest.mark.unit

_TOKEN = "s3cret-token"


def _client(*, token: str | None = _TOKEN) -> tuple[TestClient, InMemoryWorkflowRepository]:
    repo = InMemoryWorkflowRepository()
    app = create_app(
        Settings(
            app_env="development",
            database_url=None,
            redis_url=None,
            llm_provider="fake",
            scheduler_token=token,
        )
    )
    app.dependency_overrides[get_workflow_repo] = lambda: repo
    app.dependency_overrides[get_document_repo] = InMemoryDocumentRepository
    app.dependency_overrides[get_feedback_repo] = InMemoryFeedbackRepository
    return TestClient(app), repo


def _make_scheduled(client: TestClient, cron: str = "* * * * *") -> str:
    wf = client.post("/api/workflows", json={"task_description": "daily digest"}).json()
    client.patch(f"/api/workflows/{wf['id']}", json={"status": "active", "schedule_cron": cron})
    return wf["id"]


def test_tick_disabled_without_token():
    client, _ = _client(token=None)
    resp = client.post("/api/scheduler/tick", headers={"X-Scheduler-Token": "x"})
    assert resp.status_code == 503


def test_tick_rejects_bad_token():
    client, _ = _client()
    assert client.post("/api/scheduler/tick").status_code == 401
    assert (
        client.post("/api/scheduler/tick", headers={"X-Scheduler-Token": "wrong"}).status_code
        == 401
    )


def test_tick_dispatches_due_workflow():
    client, _ = _client()
    _make_scheduled(client, cron="* * * * *")  # due every minute
    resp = client.post(
        "/api/scheduler/tick?window_seconds=120", headers={"X-Scheduler-Token": _TOKEN}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert len(body["dispatched"]) == 1


def test_tick_ignores_workflow_not_yet_due():
    client, _ = _client()
    # Fires only at 03:00; with a 60s window it is (almost surely) not due right now.
    _make_scheduled(client, cron="0 3 * * *")
    resp = client.post(
        "/api/scheduler/tick?window_seconds=60", headers={"X-Scheduler-Token": _TOKEN}
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_tick_ignores_draft_workflow():
    client, _ = _client()
    # Scheduled cron but left as draft (not active) → not dispatched.
    wf = client.post("/api/workflows", json={"task_description": "x"}).json()
    client.patch(f"/api/workflows/{wf['id']}", json={"schedule_cron": "* * * * *"})
    resp = client.post(
        "/api/scheduler/tick?window_seconds=120", headers={"X-Scheduler-Token": _TOKEN}
    )
    assert resp.json()["count"] == 0

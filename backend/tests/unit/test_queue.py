"""Async run enqueue path (POST /runs with RUN_ASYNC=true)."""

import pytest
from app.config import Settings
from app.dependencies import get_document_repo, get_workflow_repo
from app.main import create_app
from app.worker import tasks
from fastapi.testclient import TestClient

from tests.fakes import InMemoryDocumentRepository, InMemoryWorkflowRepository

pytestmark = pytest.mark.unit


def test_run_async_enqueues_task_and_returns_pending(monkeypatch):
    enqueued: list[str] = []
    monkeypatch.setattr(tasks.execute_run, "delay", enqueued.append)

    repo = InMemoryWorkflowRepository()
    app = create_app(Settings(app_env="development", llm_provider="fake", run_async=True))
    app.dependency_overrides[get_workflow_repo] = lambda: repo
    app.dependency_overrides[get_document_repo] = lambda: InMemoryDocumentRepository()
    client = TestClient(app)

    wf = client.post("/api/workflows", json={"task_description": "collect news"}).json()
    resp = client.post(f"/api/workflows/{wf['id']}/runs")

    assert resp.status_code == 202  # accepted, not executed inline
    body = resp.json()
    assert body["status"] == "pending"
    assert body["step_results"] == []
    # the run id was handed to the worker
    assert enqueued == [body["id"]]


def test_run_sync_still_executes_inline_by_default(workflow_client):
    # Default settings have run_async=False → inline execution (201, gated).
    wf = workflow_client.post(
        "/api/workflows", json={"task_description": "collect news and slack me"}
    ).json()
    resp = workflow_client.post(f"/api/workflows/{wf['id']}/runs")
    assert resp.status_code == 201
    assert resp.json()["status"] == "awaiting_review"

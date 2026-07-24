"""Workflow service + CRUD route tests (offline via the in-memory repository)."""

import pytest
from app.llm.schemas import PlannedStep, WorkflowPlan
from app.models.enums import StepType, WorkflowStatus
from app.services.workflows import workflow_from_plan

pytestmark = pytest.mark.unit


_PLAN = WorkflowPlan(
    title="Morning AI news digest",
    summary="Collect, summarize, and Slack AI startup news.",
    steps=[
        PlannedStep(
            type=StepType.web_search, name="Search", description="d", config={"query": "ai"}
        ),
        PlannedStep(type=StepType.summarize, name="Summarize", description="d", config={}),
        PlannedStep(type=StepType.notify_slack, name="Notify", description="d", config={}),
    ],
)


# --- service mapping (pure) ---


def test_workflow_from_plan_orders_steps():
    wf = workflow_from_plan(description="task text", plan=_PLAN)
    assert wf.title == "Morning AI news digest"
    assert wf.description == "task text"
    assert wf.status is WorkflowStatus.draft
    assert [s.order_index for s in wf.steps] == [0, 1, 2]
    assert [s.type for s in wf.steps] == [
        StepType.web_search,
        StepType.summarize,
        StepType.notify_slack,
    ]


# --- CRUD routes (fake repo) ---


def _create(client, task="collect AI news and Slack me") -> dict:
    resp = client.post("/api/workflows", json={"task_description": task})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_workflow_uses_planner(workflow_client):
    body = _create(workflow_client)
    assert body["id"]
    assert body["status"] == "draft"
    assert len(body["steps"]) == 3
    assert body["steps"][0]["order_index"] == 0


def test_create_with_supplied_plan_skips_planner(workflow_client):
    resp = workflow_client.post(
        "/api/workflows",
        json={"task_description": "x", "plan": _PLAN.model_dump()},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Morning AI news digest"


def test_get_workflow(workflow_client):
    created = _create(workflow_client)
    resp = workflow_client.get(f"/api/workflows/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_missing_workflow_404(workflow_client):
    import uuid

    resp = workflow_client.get(f"/api/workflows/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_workflows(workflow_client):
    _create(workflow_client, "one")
    _create(workflow_client, "two")
    resp = workflow_client.get("/api/workflows")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["limit"] == 20  # default page size


def test_list_clamps_limit_to_max(workflow_client):
    resp = workflow_client.get("/api/workflows?limit=9999")
    assert resp.status_code == 200
    assert resp.json()["limit"] == 100  # api_max_page_size


def test_update_workflow_fields_and_steps(workflow_client):
    created = _create(workflow_client)
    resp = workflow_client.patch(
        f"/api/workflows/{created['id']}",
        json={
            "title": "Renamed",
            "status": "active",
            "steps": [
                {"type": "summarize", "name": "Only step", "config": {}},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Renamed"
    assert body["status"] == "active"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["type"] == "summarize"


def test_delete_workflow(workflow_client):
    created = _create(workflow_client)
    assert workflow_client.delete(f"/api/workflows/{created['id']}").status_code == 204
    assert workflow_client.get(f"/api/workflows/{created['id']}").status_code == 404


def test_list_runs_for_workflow_empty(workflow_client):
    created = _create(workflow_client)
    resp = workflow_client.get(f"/api/workflows/{created['id']}/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_missing_workflow_404(workflow_client):
    import uuid

    resp = workflow_client.get(f"/api/workflows/{uuid.uuid4()}/runs")
    assert resp.status_code == 404


# --- run execution (Step 9) ---


def test_run_workflow_pauses_for_review_before_side_effects(workflow_client):
    created = _create(workflow_client)  # search → summarize → notify_slack
    resp = workflow_client.post(f"/api/workflows/{created['id']}/runs")
    assert resp.status_code == 201, resp.text
    run = resp.json()
    # Pauses before the side-effecting notify step.
    assert run["status"] == "awaiting_review"
    assert run["workflow_id"] == created["id"]
    assert len(run["step_results"]) == 2  # search + summarize only
    assert all(sr["status"] == "succeeded" for sr in run["step_results"])
    assert run["step_results"][0]["output"]["count"] >= 1


def test_run_then_appears_in_history(workflow_client):
    created = _create(workflow_client)
    run = workflow_client.post(f"/api/workflows/{created['id']}/runs").json()
    # listed under the workflow
    listed = workflow_client.get(f"/api/workflows/{created['id']}/runs").json()
    assert [r["id"] for r in listed] == [run["id"]]
    # fetchable by id
    fetched = workflow_client.get(f"/api/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]


def test_run_missing_workflow_404(workflow_client):
    import uuid

    resp = workflow_client.post(f"/api/workflows/{uuid.uuid4()}/runs")
    assert resp.status_code == 404

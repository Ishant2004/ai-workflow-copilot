"""Feedback loop tests (Step 18) — offline via in-memory repositories.

Covers the planner few-shot mechanics, the feedback endpoints, and the end-to-end
loop: approved suggestions steer the next suggestion.
"""

import asyncio

import pytest
from app.llm.fake_planner import FakePlanner
from app.llm.prompts import build_examples_block
from app.llm.schemas import PlanExample, PlannedStep, WorkflowPlan
from app.models.enums import StepType

pytestmark = pytest.mark.unit


_APPROVED = WorkflowPlan(
    title="Research digest",
    summary="s",
    steps=[
        PlannedStep(
            type=StepType.web_search, name="Gather", description="d", config={"query": "x"}
        ),
        PlannedStep(
            type=StepType.orchestrate, name="Agents", description="d", config={"topic": "x"}
        ),
        PlannedStep(type=StepType.notify_email, name="Email", description="d", config={"to": "e"}),
    ],
)


# --- planner few-shot mechanics ---


def test_fake_planner_adopts_example_shape():
    planner = FakePlanner()
    example = PlanExample(task_description="prior task", plan=_APPROVED)
    plan = asyncio.run(planner.plan("brand new task", examples=[example]))
    # Shape mirrors the approved example, not the default search→summarize→notify.
    assert [s.type for s in plan.steps] == [
        StepType.web_search,
        StepType.orchestrate,
        StepType.notify_email,
    ]
    # Query/topic are retargeted to the new task; other config kept.
    assert plan.steps[0].config["query"] == "brand new task"
    assert plan.steps[1].config["topic"] == "brand new task"
    assert plan.steps[2].config["to"] == "e"


def test_fake_planner_ignores_empty_examples():
    plan = asyncio.run(FakePlanner().plan("task", examples=[]))
    assert [s.type for s in plan.steps][0] is StepType.web_search
    assert plan.steps[1].type is StepType.summarize


def test_build_examples_block_is_empty_without_examples():
    assert build_examples_block(None) == ""
    assert build_examples_block([]) == ""


def test_build_examples_block_renders_tasks_and_steps():
    block = build_examples_block([PlanExample(task_description="prior task", plan=_APPROVED)])
    assert "prior task" in block
    assert "orchestrate" in block


# --- feedback endpoints ---


def _create(client, task="collect AI news") -> dict:
    resp = client.post("/api/workflows", json={"task_description": task})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_submit_and_list_feedback(workflow_client):
    wf = _create(workflow_client)
    resp = workflow_client.post(
        f"/api/workflows/{wf['id']}/feedback",
        json={"rating": "positive", "comment": "spot on"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rating"] == "positive"
    assert body["workflow_id"] == wf["id"]

    listed = workflow_client.get(f"/api/workflows/{wf['id']}/feedback")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["comment"] == "spot on"


def test_feedback_on_missing_workflow_404(workflow_client):
    import uuid

    resp = workflow_client.post(
        f"/api/workflows/{uuid.uuid4()}/feedback", json={"rating": "positive"}
    )
    assert resp.status_code == 404


def test_positive_feedback_steers_next_suggestion(workflow_client):
    # 1) Create a workflow, then reshape it to an approved template.
    wf = _create(workflow_client, task="first task")
    workflow_client.patch(
        f"/api/workflows/{wf['id']}",
        json={
            "steps": [
                {"type": "web_search", "name": "Gather", "config": {"query": "x"}},
                {"type": "orchestrate", "name": "Agents", "config": {"topic": "x"}},
                {"type": "notify_email", "name": "Email", "config": {"to": "a@b"}},
            ]
        },
    )
    # 2) Rate it positively — it becomes a planning exemplar.
    workflow_client.post(f"/api/workflows/{wf['id']}/feedback", json={"rating": "positive"})
    # 3) A brand-new workflow now mirrors the approved shape (the loop).
    nxt = _create(workflow_client, task="second task")
    assert [s["type"] for s in nxt["steps"]] == ["web_search", "orchestrate", "notify_email"]
    assert nxt["steps"][0]["config"]["query"] == "second task"


def test_negative_feedback_is_not_used_as_exemplar(workflow_client):
    wf = _create(workflow_client, task="first task")
    workflow_client.post(f"/api/workflows/{wf['id']}/feedback", json={"rating": "negative"})
    # No positive exemplars → default plan shape.
    nxt = _create(workflow_client, task="second task")
    assert [s["type"] for s in nxt["steps"]] == ["web_search", "summarize", "notify_slack"]

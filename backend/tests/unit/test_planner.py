"""Planner tests — schemas, fake planner, factory, and the preview route.

No network or API key is exercised: the Anthropic path is only constructed, never
called (the fake planner covers behavior).
"""

import asyncio

import pytest
from app.config import Settings
from app.llm import WorkflowPlan, get_planner
from app.llm.anthropic_planner import AnthropicPlanner
from app.llm.fake_planner import FakePlanner
from app.llm.schemas import PlannedStep
from app.main import create_app
from app.models.enums import StepType
from fastapi.testclient import TestClient
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_workflow_plan_validates_step_types():
    plan = WorkflowPlan.model_validate(
        {
            "title": "t",
            "summary": "s",
            "steps": [
                {"type": "web_search", "name": "n", "description": "d", "config": {"query": "x"}}
            ],
        }
    )
    assert plan.steps[0].type is StepType.web_search


def test_workflow_plan_rejects_unknown_step_type():
    with pytest.raises(ValidationError):
        PlannedStep(type="teleport", name="n", description="d")  # type: ignore[arg-type]


def test_fake_planner_is_deterministic_and_typed():
    planner = FakePlanner()
    plan = asyncio.run(planner.plan("collect AI news and Slack me a digest"))
    assert isinstance(plan, WorkflowPlan)
    assert [s.type for s in plan.steps] == [
        StepType.web_search,
        StepType.summarize,
        StepType.notify_slack,
    ]
    # config carries the task-derived query
    assert plan.steps[0].config["query"].startswith("collect AI news")


def test_factory_returns_fake_for_fake_provider():
    assert isinstance(get_planner(Settings(llm_provider="fake")), FakePlanner)


def test_factory_returns_none_for_anthropic_without_key():
    assert get_planner(Settings(llm_provider="anthropic", anthropic_api_key=None)) is None


def test_factory_builds_anthropic_when_key_present():
    planner = get_planner(Settings(llm_provider="anthropic", anthropic_api_key="sk-test-xxx"))
    assert isinstance(planner, AnthropicPlanner)


def test_preview_route_returns_plan(client):
    resp = client.post("/api/planner/preview", json={"task_description": "summarize my inbox"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["steps"] and body["title"]


def test_preview_route_rejects_empty_task(client):
    resp = client.post("/api/planner/preview", json={"task_description": ""})
    assert resp.status_code == 422


def test_preview_route_503_when_planner_disabled():
    # anthropic provider + no key -> planner is None -> 503
    app = create_app(Settings(app_env="development", llm_provider="anthropic"))
    resp = TestClient(app).post("/api/planner/preview", json={"task_description": "x"})
    assert resp.status_code == 503

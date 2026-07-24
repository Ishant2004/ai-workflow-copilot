"""Multi-agent orchestration tests (offline, fake orchestrator)."""

import asyncio

import pytest
from app.agents import AgentRole, get_orchestrator
from app.agents.fake import FakeAgentOrchestrator
from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools import ToolError
from app.tools.fake import FakeNotifyTool
from app.tools.orchestrate import OrchestrateTool

pytestmark = pytest.mark.unit


def _step(**config) -> Step:
    return Step(order_index=0, type=StepType.orchestrate, name="orchestrate", config=config)


def test_orchestrator_runs_research_summarize_review_in_order():
    result = asyncio.run(
        FakeAgentOrchestrator(review_rounds=1).run("AI safety", ["fact one", "fact two"])
    )
    roles = [turn.role for turn in result.turns]
    assert roles == [AgentRole.researcher, AgentRole.summarizer, AgentRole.reviewer]
    # Research is grounded in the supplied material.
    assert "fact one" in result.turns[0].output
    assert result.review_rounds == 1
    assert "Reviewed" in result.final


def test_review_rounds_control_reviewer_turns():
    result = asyncio.run(FakeAgentOrchestrator(review_rounds=0).run("topic", []))
    assert [t.role for t in result.turns] == [AgentRole.researcher, AgentRole.summarizer]
    assert result.review_rounds == 0

    three = asyncio.run(FakeAgentOrchestrator(review_rounds=3).run("topic", []))
    assert sum(t.role is AgentRole.reviewer for t in three.turns) == 3


def test_orchestrate_tool_requires_topic():
    tool = OrchestrateTool(FakeAgentOrchestrator(review_rounds=1))
    with pytest.raises(ToolError) as exc:
        asyncio.run(tool.run(_step(), {}))
    assert exc.value.retryable is False


def test_orchestrate_tool_grounds_on_upstream_material():
    tool = OrchestrateTool(FakeAgentOrchestrator(review_rounds=1))
    context = {
        StepType.web_search.value: {"results": [{"snippet": "search snippet"}]},
        StepType.retrieve.value: {"chunks": [{"content": "doc chunk"}]},
    }
    out = asyncio.run(tool.run(_step(topic="climate"), context))
    assert out["topic"] == "climate"
    assert out["review_rounds"] == 1
    assert [t["role"] for t in out["turns"]][0] == "researcher"
    research = out["turns"][0]["output"]
    assert "search snippet" in research and "doc chunk" in research
    assert out["final"]


def test_get_orchestrator_defaults_to_fake():
    assert isinstance(get_orchestrator(Settings(tools_provider="fake")), FakeAgentOrchestrator)


def test_live_without_key_falls_back_to_fake():
    # tools_provider=live but no API key → safe fallback, run still completes.
    orch = get_orchestrator(Settings(tools_provider="live", anthropic_api_key=None))
    assert isinstance(orch, FakeAgentOrchestrator)


def test_notify_delivers_orchestrated_final_when_no_summary():
    context = {StepType.orchestrate.value: {"final": "the reviewed digest"}}
    out = asyncio.run(
        FakeNotifyTool().run(
            Step(order_index=1, type=StepType.notify_slack, name="notify", config={}),
            context,
        )
    )
    assert "the reviewed digest" in out["message_preview"]

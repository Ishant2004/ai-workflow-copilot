"""Tool implementations + registry tests."""

import asyncio

import pytest
from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools import ToolError, build_tool_registry
from app.tools.fake import FakeNotifyTool, FakeSummarizeTool, FakeWebSearchTool

pytestmark = pytest.mark.unit


def _step(step_type: StepType, **config) -> Step:
    return Step(order_index=0, type=step_type, name=step_type.value, config=config)


def test_web_search_returns_results_from_query():
    tool = FakeWebSearchTool(max_results=3)
    out = asyncio.run(tool.run(_step(StepType.web_search, query="ai news"), {}))
    assert out["count"] == 3
    assert out["query"] == "ai news"
    assert all("ai news" in r["title"] for r in out["results"])


def test_web_search_requires_query():
    tool = FakeWebSearchTool(max_results=3)
    with pytest.raises(ToolError):
        asyncio.run(tool.run(_step(StepType.web_search), {}))


def test_summarize_consumes_upstream_search():
    search_out = {"results": [{"title": "A"}, {"title": "B"}]}
    out = asyncio.run(
        FakeSummarizeTool().run(_step(StepType.summarize), {StepType.web_search.value: search_out})
    )
    assert out["source_count"] == 2
    assert "A" in out["summary"] and "B" in out["summary"]


def test_notify_previews_the_summary():
    ctx = {StepType.summarize.value: {"summary": "the digest"}}
    out = asyncio.run(FakeNotifyTool().run(_step(StepType.notify_slack, channel="#news"), ctx))
    assert out["delivered"] is False
    assert out["channel"] == "#news"
    assert "the digest" in out["message_preview"]


def test_registry_maps_all_step_types_for_fake_provider():
    registry = build_tool_registry(Settings(tools_provider="fake"))
    for step_type in StepType:
        assert registry.get(step_type) is not None

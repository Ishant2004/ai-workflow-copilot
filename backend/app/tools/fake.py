"""Deterministic, offline tool implementations.

These simulate the real actions without any network/API keys, but with real data
flow between steps — search produces results, summarize consumes them, notify
consumes the summary — so an executed run is meaningful and testable. Real
providers implement the same ``Tool`` interface and are selected via config.
"""

from __future__ import annotations

from app.models.enums import StepType
from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput


class FakeWebSearchTool(Tool):
    def __init__(self, max_results: int) -> None:
        self._max_results = max_results

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        query = str(step.config.get("query") or "").strip()
        if not query:
            raise ToolError("web_search requires a 'query' in the step config")
        results = [
            {
                "title": f"Result {i + 1} for “{query}”",
                "url": f"https://example.com/search?q={i + 1}",
                "snippet": f"Simulated result {i + 1} relevant to “{query}”.",
            }
            for i in range(self._max_results)
        ]
        return {"query": query, "count": len(results), "results": results}


class FakeSummarizeTool(Tool):
    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        search = context.get(StepType.web_search.value) or {}
        results = search.get("results", []) if isinstance(search, dict) else []
        if results:
            lines = [f"- {r.get('title', '')}" for r in results]
            summary = "Summary of findings:\n" + "\n".join(lines)
        else:
            # No upstream search — summarize whatever the step names.
            summary = f"Summary for: {step.name}"
        return {"summary": summary, "source_count": len(results)}


class FakeNotifyTool(Tool):
    """Stub for Slack/email — records what *would* be delivered (real send: Step 11)."""

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        summarize = context.get(StepType.summarize.value) or {}
        message = summarize.get("summary") if isinstance(summarize, dict) else None
        target = step.config.get("channel") or step.config.get("to") or "default"
        return {
            "delivered": False,
            "channel": str(target),
            "message_preview": (message or step.name)[:280],
            "note": "Delivery is simulated; real Slack/email arrives in Step 11.",
        }

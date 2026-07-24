"""Orchestrate tool — runs the multi-agent team as one workflow step.

Adapts the ``AgentOrchestrator`` to the ``Tool`` interface: reads the topic from
the step config, gathers any upstream material (web-search results, retrieved
document chunks) to ground the researcher, and returns the full agent trace plus
the reviewer-approved ``final`` digest for downstream steps to consume.
"""

from __future__ import annotations

from app.agents.base import AgentError, AgentOrchestrator
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput


def _gather_material(context: ExecutionContext) -> list[str]:
    """Collect grounding text from upstream search/retrieval outputs, if present."""
    material: list[str] = []

    search = context.get(StepType.web_search.value) or {}
    for result in search.get("results", []) if isinstance(search, dict) else []:
        snippet = result.get("snippet") or result.get("title")
        if snippet:
            material.append(str(snippet))

    retrieved = context.get(StepType.retrieve.value) or {}
    for chunk in retrieved.get("chunks", []) if isinstance(retrieved, dict) else []:
        content = chunk.get("content")
        if content:
            material.append(str(content))

    return material


class OrchestrateTool(Tool):
    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        topic = str(step.config.get("topic") or step.config.get("query") or "").strip()
        if not topic:
            raise ToolError(
                "orchestrate requires a 'topic' (or 'query') in the step config",
                retryable=False,
            )

        try:
            result = await self._orchestrator.run(topic, _gather_material(context))
        except AgentError as exc:
            raise ToolError(f"orchestration failed: {exc}") from exc

        return {
            "topic": result.topic,
            "final": result.final,
            "review_rounds": result.review_rounds,
            "turns": [{"role": turn.role.value, "output": turn.output} for turn in result.turns],
        }

"""Claude-backed summarizer — the real-provider example for tool execution.

Selected when ``TOOLS_PROVIDER=live`` and an Anthropic key is configured. Reuses
the same async client/config knobs as the planner. Falls back to raising a
``ToolError`` on failure so the executor records a failed step rather than crashing.
"""

from __future__ import annotations

import json
import logging

import anthropic

from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You summarize collected information into a concise, structured digest. "
    "Return 3-6 short bullet points capturing the key facts. Plain text only."
)


class ClaudeSummarizeTool(Tool):
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Claude summarizer")
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        search = context.get(StepType.web_search.value) or {}
        retrieved = context.get(StepType.retrieve.value) or {}
        scraped = context.get(StepType.scrape.value) or {}
        scrape_items = (
            [{"content": scraped["content"]}]
            if isinstance(scraped, dict) and scraped.get("content")
            else []
        )
        material_items = (
            (search.get("results", []) if isinstance(search, dict) else [])
            + (retrieved.get("chunks", []) if isinstance(retrieved, dict) else [])
            + scrape_items
        )
        material = json.dumps(material_items)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM,
                messages=[{"role": "user", "content": f"Summarize these findings:\n{material}"}],
            )
        except anthropic.APIError as exc:
            logger.warning("summarize LLM call failed: %s", exc)
            raise ToolError(f"summarization failed: {exc}") from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        return {"summary": text.strip(), "source_count": len(material_items)}

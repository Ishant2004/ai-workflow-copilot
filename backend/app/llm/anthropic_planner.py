"""Claude-backed planner.

Uses the async Anthropic SDK with a single forced tool to get structured output.
Reliability/scalability knobs — model, max tokens, timeout, retries, and a
concurrency cap — all come from config (no magic numbers). The concurrency
semaphore bounds in-flight calls per process so a burst can't exhaust resources
or overrun provider rate limits.
"""

from __future__ import annotations

import asyncio
import logging

import anthropic
from pydantic import ValidationError

from app.config import Settings
from app.llm.base import Planner, PlannerError
from app.llm.prompts import PLANNER_TOOL_NAME, SYSTEM_PROMPT, build_planner_tool
from app.llm.schemas import WorkflowPlan

logger = logging.getLogger(__name__)


class AnthropicPlanner(Planner):
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic planner")
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._tool = build_planner_tool()
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    async def plan(self, task_description: str) -> WorkflowPlan:
        async with self._semaphore:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=SYSTEM_PROMPT,
                    tools=[self._tool],
                    tool_choice={"type": "tool", "name": PLANNER_TOOL_NAME},
                    messages=[{"role": "user", "content": task_description}],
                )
            except anthropic.APIError as exc:
                logger.warning("planner LLM call failed: %s", exc)
                raise PlannerError(f"LLM request failed: {exc}") from exc

        tool_input = next((b.input for b in response.content if b.type == "tool_use"), None)
        if tool_input is None:
            raise PlannerError("model did not return a workflow plan")

        try:
            return WorkflowPlan.model_validate(tool_input)
        except ValidationError as exc:
            logger.warning("planner returned invalid plan: %s", exc)
            raise PlannerError(f"model returned an invalid plan: {exc}") from exc

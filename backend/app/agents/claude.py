"""Claude-backed multi-agent orchestrator.

Runs the researcher → summarizer → reviewer team as a sequence of role-specialized
Claude calls, threading each agent's output into the next. Reuses the same client
knobs as the planner/summarizer (model, tokens, timeout, retries) — no magic
numbers — and a per-instance concurrency cap so one orchestration's fan-out of
calls can't exhaust the process or overrun provider rate limits.
"""

from __future__ import annotations

import asyncio
import logging

import anthropic

from app.agents.base import AgentError, AgentOrchestrator, AgentRole, AgentTurn, OrchestrationResult
from app.agents.prompts import RESEARCHER_SYSTEM, REVIEWER_SYSTEM, SUMMARIZER_SYSTEM
from app.config import Settings

logger = logging.getLogger(__name__)


class ClaudeAgentOrchestrator(AgentOrchestrator):
    def __init__(self, settings: Settings, review_rounds: int) -> None:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Claude orchestrator")
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._review_rounds = max(0, review_rounds)
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    async def run(self, topic: str, material: list[str]) -> OrchestrationResult:
        turns: list[AgentTurn] = []

        material_block = "\n".join(f"- {m}" for m in material if m) or "(no source material)"
        research = await self._ask(
            RESEARCHER_SYSTEM,
            f"Topic: {topic}\n\nSource material:\n{material_block}",
        )
        turns.append(AgentTurn(AgentRole.researcher, research))

        draft = await self._ask(SUMMARIZER_SYSTEM, f"Researcher findings:\n{research}")
        turns.append(AgentTurn(AgentRole.summarizer, draft))

        current = draft
        for _ in range(self._review_rounds):
            current = await self._ask(REVIEWER_SYSTEM, f"Draft digest to review:\n{current}")
            turns.append(AgentTurn(AgentRole.reviewer, current))

        return OrchestrationResult(
            topic=topic,
            final=current,
            turns=turns,
            review_rounds=self._review_rounds,
        )

    async def _ask(self, system: str, user: str) -> str:
        async with self._semaphore:
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
            except anthropic.APIError as exc:
                logger.warning("agent call failed: %s", exc)
                raise AgentError(f"agent call failed: {exc}") from exc
        return "".join(block.text for block in response.content if block.type == "text").strip()

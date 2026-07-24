"""Multi-agent orchestration package.

`get_orchestrator` selects the implementation the same way the tool registry
selects tools: the deterministic fake by default, the Claude-backed team when
``TOOLS_PROVIDER=live`` and an Anthropic key is configured (falling back to the
fake otherwise so a run still completes).
"""

from __future__ import annotations

import logging

from app.agents.base import (
    AgentError,
    AgentOrchestrator,
    AgentRole,
    AgentTurn,
    OrchestrationResult,
)
from app.agents.fake import FakeAgentOrchestrator
from app.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "AgentError",
    "AgentOrchestrator",
    "AgentRole",
    "AgentTurn",
    "OrchestrationResult",
    "get_orchestrator",
]


def get_orchestrator(settings: Settings) -> AgentOrchestrator:
    rounds = settings.agent_review_rounds
    if settings.tools_provider.lower() == "live":
        if settings.anthropic_api_key:
            from app.agents.claude import ClaudeAgentOrchestrator  # noqa: PLC0415

            return ClaudeAgentOrchestrator(settings, review_rounds=rounds)
        logger.warning(
            "TOOLS_PROVIDER=live but ANTHROPIC_API_KEY is unset; using the fake orchestrator."
        )
    return FakeAgentOrchestrator(review_rounds=rounds)

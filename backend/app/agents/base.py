"""Multi-agent orchestration interface.

The `orchestrate` step delegates to a small team of role-specialized agents that
collaborate on one task:

- **researcher** — gathers and organizes the raw findings (from upstream
  search/retrieval material, or the topic itself);
- **summarizer** — distills the findings into a concise draft digest;
- **reviewer** — critiques the draft for accuracy/completeness and returns an
  improved version. Runs for a configurable number of rounds.

Like every other provider in this codebase (planner, tools, embedder) the
orchestrator lives behind an interface so a deterministic offline fake can stand
in for the real Claude-backed team in dev and tests (ADR-002).
"""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass


class AgentRole(str, enum.Enum):
    researcher = "researcher"
    summarizer = "summarizer"
    reviewer = "reviewer"


@dataclass(frozen=True)
class AgentTurn:
    """One agent's contribution — kept so the full collaboration is auditable."""

    role: AgentRole
    output: str


@dataclass(frozen=True)
class OrchestrationResult:
    topic: str
    final: str  # the reviewer-approved digest downstream steps consume
    turns: list[AgentTurn]  # ordered trace of every agent turn
    review_rounds: int


class AgentOrchestrator(abc.ABC):
    """Coordinates the researcher → summarizer → reviewer team for one task."""

    @abc.abstractmethod
    async def run(self, topic: str, material: list[str]) -> OrchestrationResult:
        """Run the agent team over ``topic`` (grounded in ``material``, if any).

        Raises:
            AgentError: if the collaboration cannot produce a result.
        """
        raise NotImplementedError


class AgentError(RuntimeError):
    """Raised when the agent team cannot complete its task."""

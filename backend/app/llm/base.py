"""Planner interface.

The LLM provider is isolated behind this abstract base class (ADR-002) so the
Anthropic implementation can be swapped — for a different model/provider, or for
the deterministic ``FakePlanner`` in tests — without touching callers.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence

from app.llm.schemas import PlanExample, WorkflowPlan


class PlannerError(RuntimeError):
    """Raised when the planner cannot produce a valid workflow plan."""


class Planner(abc.ABC):
    """Turns a plain-English task description into a structured workflow plan."""

    @abc.abstractmethod
    async def plan(
        self,
        task_description: str,
        *,
        examples: Sequence[PlanExample] | None = None,
    ) -> WorkflowPlan:
        """Return a structured plan for ``task_description``.

        ``examples`` are past, positively-rated suggestions (from the feedback
        loop) the planner may use as few-shot guidance for shapes users approve of.

        Raises:
            PlannerError: if a valid plan could not be produced.
        """
        raise NotImplementedError

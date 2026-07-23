"""Planner interface.

The LLM provider is isolated behind this abstract base class (ADR-002) so the
Anthropic implementation can be swapped — for a different model/provider, or for
the deterministic ``FakePlanner`` in tests — without touching callers.
"""

from __future__ import annotations

import abc

from app.llm.schemas import WorkflowPlan


class PlannerError(RuntimeError):
    """Raised when the planner cannot produce a valid workflow plan."""


class Planner(abc.ABC):
    """Turns a plain-English task description into a structured workflow plan."""

    @abc.abstractmethod
    async def plan(self, task_description: str) -> WorkflowPlan:
        """Return a structured plan for ``task_description``.

        Raises:
            PlannerError: if a valid plan could not be produced.
        """
        raise NotImplementedError

"""Structured output schemas for the planner.

These mirror the domain model (``StepType`` is shared with the ORM) so a generated
plan maps cleanly onto ``Workflow`` + ``Step`` rows when it's persisted (Step 6).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import StepType


class PlannedStep(BaseModel):
    """One typed, ordered step the planner proposes."""

    type: StepType
    name: str
    description: str
    # Tool parameters (e.g. {"query": "..."} for web_search). Shape varies by type.
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowPlan(BaseModel):
    """A structured plan derived from a plain-English task description."""

    title: str
    summary: str
    steps: list[PlannedStep]


class PlanExample(BaseModel):
    """A past, positively-rated (task → plan) pair used to steer new suggestions.

    Sourced from user feedback (Step 18) so the planner learns the shapes users
    approve of — the "feedback loop to improve workflow suggestions".
    """

    task_description: str
    plan: WorkflowPlan

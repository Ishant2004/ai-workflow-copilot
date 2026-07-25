"""Workflow domain helpers — pure, DB-free mapping between plans/DTOs and ORM.

Keeping these pure makes them unit-testable without a database and keeps the
repository focused on persistence.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.llm.schemas import PlannedStep, WorkflowPlan
from app.models.enums import WorkflowStatus
from app.models.workflow import Step, Workflow
from app.schemas.workflow import StepIn


def steps_from_plan(plan: WorkflowPlan) -> list[Step]:
    """Build ordered Step ORM objects from a planner plan."""
    return [
        Step(
            order_index=i,
            type=step.type,
            name=step.name,
            description=step.description,
            config=step.config,
        )
        for i, step in enumerate(plan.steps)
    ]


def steps_from_input(steps: Sequence[StepIn]) -> list[Step]:
    """Build ordered Step ORM objects from API input (list order = execution order)."""
    return [
        Step(
            order_index=i,
            type=step.type,
            name=step.name,
            description=step.description,
            config=step.config,
        )
        for i, step in enumerate(steps)
    ]


def workflow_from_plan(*, description: str, plan: WorkflowPlan) -> Workflow:
    """Build a transient Workflow (with steps) from a plan, ready to persist."""
    return Workflow(
        title=plan.title,
        description=description,
        status=WorkflowStatus.draft,
        steps=steps_from_plan(plan),
    )


def plan_from_workflow(workflow: Workflow) -> WorkflowPlan:
    """Snapshot a workflow's current shape as a plan (for feedback exemplars)."""
    ordered = sorted(workflow.steps, key=lambda s: s.order_index)
    return WorkflowPlan(
        title=workflow.title,
        summary=workflow.description,
        steps=[
            PlannedStep(
                type=step.type,
                name=step.name,
                description=step.description or "",
                config=step.config,
            )
            for step in ordered
        ],
    )

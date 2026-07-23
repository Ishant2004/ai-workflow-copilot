"""Deterministic planner for local dev and tests — no network, no API key.

Produces a plausible search → summarize → notify plan from the task text so the
rest of the pipeline can be built and tested offline. Selected via
``LLM_PROVIDER=fake`` (the default in .env.development).
"""

from __future__ import annotations

from app.llm.base import Planner
from app.llm.schemas import PlannedStep, WorkflowPlan
from app.models.enums import StepType


class FakePlanner(Planner):
    async def plan(self, task_description: str) -> WorkflowPlan:
        task = task_description.strip()
        title = (task[:57] + "...") if len(task) > 60 else task or "Untitled workflow"
        return WorkflowPlan(
            title=title,
            summary=f"Auto-generated plan for: {task}",
            steps=[
                PlannedStep(
                    type=StepType.web_search,
                    name="Search sources",
                    description="Search the web for information relevant to the task.",
                    config={"query": task},
                ),
                PlannedStep(
                    type=StepType.summarize,
                    name="Summarize findings",
                    description="Summarize and structure the collected information.",
                    config={},
                ),
                PlannedStep(
                    type=StepType.notify_slack,
                    name="Send digest",
                    description="Deliver the summary to the user for review.",
                    config={"channel": "#general"},
                ),
            ],
        )

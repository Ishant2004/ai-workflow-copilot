"""Deterministic planner for local dev and tests — no network, no API key.

Produces a plausible search → summarize → notify plan from the task text so the
rest of the pipeline can be built and tested offline. Selected via
``LLM_PROVIDER=fake`` (the default in .env.development).

To exercise the feedback loop (Step 18) offline, when positively-rated
``examples`` are supplied the fake adopts the step *shape* (types/names/config) of
the most recent one — so learned exemplars visibly change its suggestions, exactly
as few-shot examples steer the real planner.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.llm.base import Planner
from app.llm.schemas import PlanExample, PlannedStep, WorkflowPlan
from app.models.enums import StepType


class FakePlanner(Planner):
    async def plan(
        self,
        task_description: str,
        *,
        examples: Sequence[PlanExample] | None = None,
    ) -> WorkflowPlan:
        task = task_description.strip()
        title = (task[:57] + "...") if len(task) > 60 else task or "Untitled workflow"

        if examples:
            # Learn from the most recent approved suggestion: reuse its step shape.
            template = examples[0].plan
            return WorkflowPlan(
                title=title,
                summary=f"Plan for '{task}', shaped by {len(examples)} approved example(s).",
                steps=[
                    PlannedStep(
                        type=step.type,
                        name=step.name,
                        description=step.description,
                        config=self._retarget_config(step.config, task),
                    )
                    for step in template.steps
                ],
            )

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

    @staticmethod
    def _retarget_config(config: dict, task: str) -> dict:
        """Point an example step's query/topic at the new task, keeping other params."""
        updated = dict(config)
        if "query" in updated:
            updated["query"] = task
        if "topic" in updated:
            updated["topic"] = task
        return updated

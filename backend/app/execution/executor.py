"""Workflow executor with a human-in-the-loop review gate.

Runs a workflow's steps in order, threading each step's output into a shared
context for downstream steps, and records a ``Run`` with one ``StepResult`` per
executed step. Each tool call is bounded by a timeout so a hung tool can't block
indefinitely. On the first failure the run stops and is marked ``failed``.

Human-in-the-loop: when ``require_review`` is set, the run pauses at
``awaiting_review`` *before* the first side-effecting step (Slack/email) — the user
reviews/edits the produced result and then approves (``resume``) or rejects. This
enforces the "nothing side-effecting runs without review" principle.

Execution is synchronous here; Step 12 moves it onto a queue/worker.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.models.enums import RunStatus, StepResultStatus, StepType
from app.models.run import Run, StepResult
from app.models.workflow import Step, Workflow
from app.tools import ToolError, ToolRegistry

logger = logging.getLogger(__name__)

# Steps that have external side effects and therefore require review first.
SIDE_EFFECTING_STEP_TYPES: frozenset[StepType] = frozenset(
    {StepType.notify_slack, StepType.notify_email}
)

_FAILED_EXCEPTIONS = (ToolError, KeyError, TimeoutError)


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowExecutor:
    def __init__(self, registry: ToolRegistry, timeout_seconds: float) -> None:
        self._registry = registry
        self._timeout = timeout_seconds

    async def run(self, workflow: Workflow, *, require_review: bool = True) -> Run:
        """Execute from the start, pausing before the first side-effecting step."""
        run = Run(
            workflow_id=workflow.id,
            status=RunStatus.running,
            started_at=_now(),
        )
        run.step_results = []
        await self._execute(workflow, run, context={}, start_index=0, require_review=require_review)
        return run

    async def resume(self, workflow: Workflow, run: Run) -> Run:
        """Resume an approved run: execute the remaining steps (no further gating)."""
        context = self._rebuild_context(workflow, run)
        start_index = len(run.step_results)
        run.status = RunStatus.running
        run.finished_at = None
        await self._execute(
            workflow, run, context=context, start_index=start_index, require_review=False
        )
        return run

    # --- internals ---

    async def _execute(
        self,
        workflow: Workflow,
        run: Run,
        *,
        context: dict,
        start_index: int,
        require_review: bool,
    ) -> None:
        steps = sorted(workflow.steps, key=lambda s: s.order_index)
        overall = RunStatus.succeeded

        for step in steps[start_index:]:
            if require_review and step.type in SIDE_EFFECTING_STEP_TYPES:
                # Pause before the side-effecting step for human review.
                run.status = RunStatus.awaiting_review
                run.finished_at = None
                return

            result = await self._run_step(step, context)
            run.step_results.append(result)
            if result.status is StepResultStatus.failed:
                overall = RunStatus.failed
                break

        run.status = overall
        run.finished_at = _now()

    async def _run_step(self, step: Step, context: dict) -> StepResult:
        result = StepResult(
            step_id=step.id,
            status=StepResultStatus.running,
            started_at=_now(),
        )
        try:
            tool = self._registry.get(step.type)
            output = await asyncio.wait_for(tool.run(step, context), timeout=self._timeout)
            result.output = output
            result.status = StepResultStatus.succeeded
            context[step.type.value] = output
        except _FAILED_EXCEPTIONS as exc:
            logger.warning("step %s failed: %s", step.name, exc)
            result.status = StepResultStatus.failed
            result.error = str(exc)
        result.finished_at = _now()
        return result

    @staticmethod
    def _rebuild_context(workflow: Workflow, run: Run) -> dict:
        """Reconstruct the step context from a paused run's persisted outputs.

        Uses each executed step's (possibly edited) output, keyed by step type, so
        downstream steps see any edits the user made during review.
        """
        step_types = {step.id: step.type for step in workflow.steps}
        context: dict = {}
        for result in run.step_results:
            if result.status is StepResultStatus.succeeded and result.output is not None:
                step_type = step_types.get(result.step_id)
                if step_type is not None:
                    context[step_type.value] = result.output
        return context

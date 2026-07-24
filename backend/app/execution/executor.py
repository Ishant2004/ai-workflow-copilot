"""Workflow executor.

Runs a workflow's steps in order, threading each step's output into a shared
context for downstream steps, and records a ``Run`` with one ``StepResult`` per
executed step. Each tool call is bounded by a timeout (from config) so a hung
tool can't block indefinitely. On the first failure the run stops and is marked
failed — remaining steps are left unexecuted.

Execution is synchronous here; Step 12 moves it onto a queue/worker.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.models.enums import RunStatus, StepResultStatus
from app.models.run import Run, StepResult
from app.models.workflow import Workflow
from app.tools import ToolError, ToolRegistry

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowExecutor:
    def __init__(self, registry: ToolRegistry, timeout_seconds: float) -> None:
        self._registry = registry
        self._timeout = timeout_seconds

    async def run(self, workflow: Workflow) -> Run:
        run = Run(
            workflow_id=workflow.id,
            status=RunStatus.running,
            started_at=_now(),
        )
        context: dict = {}
        results: list[StepResult] = []
        overall = RunStatus.succeeded

        for step in sorted(workflow.steps, key=lambda s: s.order_index):
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
                # Expose this step's output to later steps.
                context[step.type.value] = output
            except (ToolError, KeyError, TimeoutError) as exc:
                logger.warning("step %s failed: %s", step.name, exc)
                result.status = StepResultStatus.failed
                result.error = str(exc)
                overall = RunStatus.failed
            result.finished_at = _now()
            results.append(result)
            if overall is RunStatus.failed:
                break

        run.step_results = results
        run.status = overall
        run.finished_at = _now()
        return run

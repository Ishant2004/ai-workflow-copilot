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

from app.logging_config import run_id_ctx
from app.models.enums import RunStatus, StepResultStatus, StepType
from app.models.run import Run, StepResult
from app.models.workflow import Step, Workflow
from app.rag.retriever import Retriever
from app.tools import ToolError, ToolRegistry
from app.tools.retrieve import RETRIEVER_CONTEXT_KEY

logger = logging.getLogger(__name__)

# Steps that have external side effects and therefore require review first.
SIDE_EFFECTING_STEP_TYPES: frozenset[StepType] = frozenset(
    {StepType.notify_slack, StepType.notify_email}
)


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        timeout_seconds: float,
        *,
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self._registry = registry
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds

    async def run(
        self,
        workflow: Workflow,
        *,
        require_review: bool = True,
        retriever: Retriever | None = None,
    ) -> Run:
        """Create a fresh Run and execute it (synchronous path)."""
        run = Run(workflow_id=workflow.id, status=RunStatus.pending)
        run.step_results = []
        await self.execute_run(workflow, run, require_review=require_review, retriever=retriever)
        return run

    async def execute_run(
        self,
        workflow: Workflow,
        run: Run,
        *,
        require_review: bool = True,
        retriever: Retriever | None = None,
    ) -> Run:
        """Execute an existing (pending) run from the start.

        Used by the async worker: the run is persisted first, then executed.
        """
        if run.step_results is None:
            run.step_results = []
        run.status = RunStatus.running
        run.started_at = _now()
        token = run_id_ctx.set(str(run.id) if run.id else None)
        try:
            await self._execute(
                workflow,
                run,
                context=self._new_context(retriever),
                start_index=len(run.step_results),
                require_review=require_review,
            )
        finally:
            run_id_ctx.reset(token)
        return run

    async def resume(
        self, workflow: Workflow, run: Run, *, retriever: Retriever | None = None
    ) -> Run:
        """Resume an approved run: execute the remaining steps (no further gating)."""
        context = self._rebuild_context(workflow, run)
        context.update(self._new_context(retriever))
        start_index = len(run.step_results)
        run.status = RunStatus.running
        run.finished_at = None
        await self._execute(
            workflow, run, context=context, start_index=start_index, require_review=False
        )
        return run

    @staticmethod
    def _new_context(retriever: Retriever | None) -> dict:
        # The retriever is a runtime capability, not step output — it isn't persisted.
        return {RETRIEVER_CONTEXT_KEY: retriever} if retriever is not None else {}

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
        log_ctx = {"step": step.name, "step_type": step.type.value}
        logger.info("step started", extra=log_ctx)

        try:
            tool = self._registry.get(step.type)
        except KeyError as exc:
            return self._fail(result, exc, log_ctx)

        last_error: Exception | None = None
        for attempt in range(1 + self._max_retries):
            try:
                output = await asyncio.wait_for(tool.run(step, context), timeout=self._timeout)
                result.output = output
                result.status = StepResultStatus.succeeded
                context[step.type.value] = output
                result.finished_at = _now()
                logger.info("step succeeded", extra={**log_ctx, "attempt": attempt + 1})
                return result
            except (ToolError, TimeoutError) as exc:
                last_error = exc
                retryable = not (isinstance(exc, ToolError) and not exc.retryable)
                if not retryable or attempt >= self._max_retries:
                    break
                delay = self._retry_backoff * (2**attempt)
                logger.warning(
                    "step retry",
                    extra={**log_ctx, "attempt": attempt + 1, "error": str(exc), "delay": delay},
                )
                await asyncio.sleep(delay)

        return self._fail(result, last_error, log_ctx)

    @staticmethod
    def _fail(result: StepResult, exc: Exception | None, log_ctx: dict) -> StepResult:
        result.status = StepResultStatus.failed
        result.error = str(exc) if exc else "unknown error"
        result.finished_at = _now()
        logger.warning("step failed", extra={**log_ctx, "error": result.error})
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

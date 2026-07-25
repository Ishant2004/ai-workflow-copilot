"""Eval harness runner.

For each case: generate a plan, execute it end-to-end (fake tools, no review gate),
then score the produced run with every evaluator. Returns a structured report the
CLI can print and gate CI on. Uses the same provider selection as the app, so with
the fake providers it runs fully offline and deterministically.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.eval.base import CaseReport, EvalCase, EvalContext, EvalReport, Evaluator
from app.eval.checks import GroundingEvaluator, PlanStructureEvaluator, RunSuccessEvaluator
from app.eval.dataset import load_cases
from app.execution.executor import WorkflowExecutor
from app.llm import Planner, PlannerError, get_planner
from app.services.workflows import workflow_from_plan
from app.tools import build_tool_registry

logger = logging.getLogger(__name__)


class EvalHarness:
    def __init__(
        self,
        planner: Planner,
        executor: WorkflowExecutor,
        evaluators: list[Evaluator],
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._evaluators = evaluators

    async def run(self, cases: list[EvalCase]) -> EvalReport:
        report = EvalReport()
        for case in cases:
            report.cases.append(await self._run_case(case))
        return report

    async def _run_case(self, case: EvalCase) -> CaseReport:
        case_report = CaseReport(case_name=case.name)
        try:
            plan = await self._planner.plan(case.task_description)
        except PlannerError as exc:
            case_report.checks.append(_failed_check("planning", f"planner failed: {exc}"))
            return case_report

        workflow = workflow_from_plan(description=case.task_description, plan=plan)
        # No review gate: execute the whole plan so downstream steps produce output.
        run = await self._executor.run(workflow, require_review=False)

        ctx = EvalContext(case=case, plan=plan, run=run)
        for evaluator in self._evaluators:
            case_report.checks.append(evaluator.evaluate(ctx))
        return case_report


def _failed_check(name: str, detail: str):
    from app.eval.base import CheckResult  # noqa: PLC0415

    return CheckResult(name, passed=False, score=0.0, detail=detail)


def build_harness(settings: Settings) -> EvalHarness:
    """Assemble a harness from config (planner, fake-tool executor, evaluators)."""
    planner = get_planner(settings)
    if planner is None:
        raise RuntimeError("no planner configured; set LLM_PROVIDER=fake or an API key")
    executor = WorkflowExecutor(
        build_tool_registry(settings),
        settings.tool_timeout_seconds,
        max_retries=settings.step_max_retries,
        retry_backoff_seconds=settings.step_retry_backoff_seconds,
    )
    evaluators: list[Evaluator] = [
        PlanStructureEvaluator(),
        RunSuccessEvaluator(),
        GroundingEvaluator(settings.eval_grounding_threshold),
    ]
    return EvalHarness(planner, executor, evaluators)


async def run_eval(settings: Settings) -> EvalReport:
    """Convenience: build the harness and run it over the configured dataset."""
    harness = build_harness(settings)
    return await harness.run(load_cases(settings.eval_dataset_path))

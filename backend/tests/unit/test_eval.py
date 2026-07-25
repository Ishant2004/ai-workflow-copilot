"""Evaluation harness tests (Step 19) — pure checks + offline end-to-end run."""

import asyncio
import json

import pytest
from app.config import Settings
from app.eval.base import EvalCase, EvalContext
from app.eval.checks import GroundingEvaluator, PlanStructureEvaluator, RunSuccessEvaluator
from app.eval.dataset import DEFAULT_CASES, load_cases
from app.eval.grounding import grounding_score
from app.eval.runner import run_eval
from app.llm.schemas import PlannedStep, WorkflowPlan
from app.models.enums import StepResultStatus, StepType
from app.models.run import Run, StepResult

pytestmark = pytest.mark.unit


# --- grounding score (pure) ---


def test_grounding_full_support():
    assert grounding_score("apples and oranges", ["fresh apples", "ripe oranges"]) == 1.0


def test_grounding_no_support_when_sources_empty():
    assert grounding_score("apples oranges", []) == 0.0


def test_grounding_empty_text_is_fully_grounded():
    # Nothing is claimed, so nothing can be hallucinated.
    assert grounding_score("the of and", ["anything"]) == 1.0


def test_grounding_partial():
    score = grounding_score("apples helicopters", ["fresh apples only"])
    assert score == pytest.approx(0.5)


# --- evaluators ---


def _ctx(steps: list[PlannedStep], outputs: list[dict | None], case: EvalCase) -> EvalContext:
    plan = WorkflowPlan(title="t", summary="s", steps=steps)
    run = Run(status=StepResultStatus.succeeded)  # status unused by checks
    run.step_results = [
        StepResult(
            status=StepResultStatus.succeeded if out is not None else StepResultStatus.failed,
            output=out,
            error=None if out is not None else "boom",
        )
        for out in outputs
    ]
    return EvalContext(case=case, plan=plan, run=run)


_CASE = EvalCase(name="c", task_description="t", expect_step_types=("web_search",))


def test_plan_structure_passes_for_sound_plan():
    steps = [
        PlannedStep(type=StepType.web_search, name="s", description="d", config={"query": "x"}),
        PlannedStep(type=StepType.summarize, name="sum", description="d", config={}),
        PlannedStep(type=StepType.notify_slack, name="n", description="d", config={}),
    ]
    result = PlanStructureEvaluator().evaluate(_ctx(steps, [{}, {}, {}], _CASE))
    assert result.passed


def test_plan_structure_flags_missing_config_and_bad_order():
    steps = [
        PlannedStep(type=StepType.summarize, name="sum", description="d", config={}),
        PlannedStep(type=StepType.web_search, name="s", description="d", config={}),  # no query
    ]
    result = PlanStructureEvaluator().evaluate(_ctx(steps, [{}, {}], _CASE))
    assert not result.passed
    assert "summarize" in result.detail and "query" in result.detail


def test_run_success_flags_failed_step():
    steps = [
        PlannedStep(type=StepType.web_search, name="s", description="d", config={"query": "x"})
    ]
    result = RunSuccessEvaluator().evaluate(_ctx(steps, [None], _CASE))
    assert not result.passed
    assert "failed" in result.detail


def test_grounding_evaluator_detects_hallucination():
    steps = [
        PlannedStep(type=StepType.web_search, name="s", description="d", config={"query": "x"}),
        PlannedStep(type=StepType.summarize, name="sum", description="d", config={}),
    ]
    outputs = [
        {"results": [{"snippet": "apples oranges bananas"}]},
        {"summary": "quantum helicopter tuesday saturn"},
    ]
    result = GroundingEvaluator(threshold=0.5).evaluate(_ctx(steps, outputs, _CASE))
    assert not result.passed
    assert result.score < 0.5


def test_grounding_evaluator_passes_grounded_digest():
    steps = [
        PlannedStep(type=StepType.web_search, name="s", description="d", config={"query": "x"}),
        PlannedStep(type=StepType.summarize, name="sum", description="d", config={}),
    ]
    outputs = [
        {"results": [{"snippet": "solar battery recycling breakthrough"}]},
        {"summary": "battery recycling breakthrough via solar"},
    ]
    result = GroundingEvaluator(threshold=0.5).evaluate(_ctx(steps, outputs, _CASE))
    assert result.passed


# --- dataset + end-to-end harness ---


def test_load_cases_defaults_and_from_file(tmp_path):
    assert load_cases(None) == list(DEFAULT_CASES)
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            [{"name": "x", "task_description": "do a thing", "expect_step_types": ["summarize"]}]
        )
    )
    cases = load_cases(str(path))
    assert len(cases) == 1 and cases[0].expect_step_types == ("summarize",)


def test_harness_runs_default_dataset_offline():
    report = asyncio.run(run_eval(Settings(llm_provider="fake", tools_provider="fake")))
    assert report.total == len(DEFAULT_CASES)
    assert report.pass_rate == 1.0
    # Every case ran all three checks.
    assert all(len(c.checks) == 3 for c in report.cases)

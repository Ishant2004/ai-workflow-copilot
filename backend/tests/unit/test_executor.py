"""Workflow executor tests (offline, fake tools)."""

import asyncio
from uuid import uuid4

import pytest
from app.config import Settings
from app.execution.executor import WorkflowExecutor
from app.models.enums import RunStatus, StepResultStatus, StepType
from app.models.workflow import Step, Workflow
from app.tools import ToolRegistry, build_tool_registry
from app.tools.base import Tool

pytestmark = pytest.mark.unit


def _workflow(*types: StepType) -> Workflow:
    wf = Workflow(title="t", description="d")
    wf.id = uuid4()
    wf.steps = [
        Step(id=uuid4(), order_index=i, type=t, name=t.value, config={"query": "ai"})
        for i, t in enumerate(types)
    ]
    return wf


def _executor() -> WorkflowExecutor:
    return WorkflowExecutor(build_tool_registry(Settings(tools_provider="fake")), 30.0)


def test_run_succeeds_and_threads_context_without_review():
    wf = _workflow(StepType.web_search, StepType.summarize, StepType.notify_slack)
    run = asyncio.run(_executor().run(wf, require_review=False))

    assert run.status is RunStatus.succeeded
    assert run.started_at and run.finished_at
    assert [r.status for r in run.step_results] == [StepResultStatus.succeeded] * 3
    # summarize consumed the web_search output threaded through context
    assert run.step_results[1].output["source_count"] >= 1


def test_run_pauses_before_side_effecting_step():
    wf = _workflow(StepType.web_search, StepType.summarize, StepType.notify_slack)
    run = asyncio.run(_executor().run(wf, require_review=True))

    assert run.status is RunStatus.awaiting_review
    assert len(run.step_results) == 2  # notify not executed yet


def test_resume_runs_remaining_steps_with_edited_context():
    wf = _workflow(StepType.web_search, StepType.summarize, StepType.notify_slack)
    executor = _executor()
    run = asyncio.run(executor.run(wf, require_review=True))
    # simulate an edit to the summarize output before approval
    run.step_results[1].output = {"summary": "EDITED"}

    asyncio.run(executor.resume(wf, run))
    assert run.status is RunStatus.succeeded
    assert len(run.step_results) == 3
    assert "EDITED" in run.step_results[2].output["message_preview"]


def test_run_stops_on_first_failure():
    # web_search with no query -> ToolError -> run fails, later steps skipped
    wf = Workflow(title="t", description="d")
    wf.id = uuid4()
    wf.steps = [
        Step(id=uuid4(), order_index=0, type=StepType.web_search, name="s", config={}),
        Step(id=uuid4(), order_index=1, type=StepType.summarize, name="sum", config={}),
    ]
    run = asyncio.run(_executor().run(wf))

    assert run.status is RunStatus.failed
    assert len(run.step_results) == 1  # stopped after the failing step
    assert run.step_results[0].status is StepResultStatus.failed
    assert run.step_results[0].error


def test_run_times_out_slow_tool():
    class SlowTool(Tool):
        async def run(self, step, context):
            await asyncio.sleep(1)
            return {}

    registry = ToolRegistry({StepType.web_search: SlowTool()})
    executor = WorkflowExecutor(registry, timeout_seconds=0.05)
    wf = _workflow(StepType.web_search)
    run = asyncio.run(executor.run(wf))
    assert run.status is RunStatus.failed
    assert run.step_results[0].status is StepResultStatus.failed


def test_missing_tool_is_recorded_as_failure():
    registry = ToolRegistry({})  # no tools registered
    executor = WorkflowExecutor(registry, 30.0)
    run = asyncio.run(executor.run(_workflow(StepType.web_search)))
    assert run.status is RunStatus.failed

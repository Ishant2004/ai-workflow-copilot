"""Cron scheduling logic + dispatch (pure, offline)."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.models.enums import WorkflowStatus
from app.models.workflow import Workflow
from app.worker.scheduling import dispatch_due, due_workflows, is_due

pytestmark = pytest.mark.unit

WINDOW = 60.0


def test_every_minute_cron_is_always_due():
    assert is_due("* * * * *", datetime(2026, 7, 24, 9, 0, 30, tzinfo=UTC), WINDOW)


def test_daily_cron_due_only_within_window_after_fire_time():
    cron = "0 9 * * *"  # 09:00 daily
    assert is_due(cron, datetime(2026, 7, 24, 9, 0, 30, tzinfo=UTC), WINDOW)  # 30s after
    assert not is_due(cron, datetime(2026, 7, 24, 10, 0, 0, tzinfo=UTC), WINDOW)  # an hour later


def test_invalid_cron_is_not_due():
    assert not is_due("not a cron", datetime.now(UTC), WINDOW)


def _wf(cron: str | None, status: WorkflowStatus = WorkflowStatus.active) -> Workflow:
    wf = Workflow(title="t", description="d", status=status, schedule_cron=cron)
    wf.id = uuid4()
    return wf


def test_due_workflows_filters_by_cron():
    now = datetime(2026, 7, 24, 9, 0, 30, tzinfo=UTC)
    wfs = [_wf("* * * * *"), _wf("0 9 * * *"), _wf("0 10 * * *"), _wf(None)]
    due = due_workflows(wfs, now, WINDOW)
    assert len(due) == 2  # every-minute + 09:00 (not 10:00, not None)


def test_dispatch_creates_and_enqueues_runs_for_due_workflows():
    wf = _wf("* * * * *")
    enqueued: list[str] = []
    created = []

    async def list_scheduled():
        return [wf]

    async def create_run(run):
        run.id = uuid4()
        created.append(run)
        return run

    ids = asyncio.run(
        dispatch_due(
            list_scheduled=list_scheduled,
            create_run=create_run,
            enqueue=enqueued.append,
            now=datetime.now(UTC),
            window_seconds=WINDOW,
        )
    )
    assert len(ids) == 1
    assert len(created) == 1
    assert enqueued == [str(ids[0])]

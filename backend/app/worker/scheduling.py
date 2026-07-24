"""Cron scheduling logic.

Pure helpers (`is_due`, `due_workflows`) decide which scheduled workflows should
fire in the current dispatch window, and `dispatch_due` turns that into persisted
pending runs + enqueue calls. Kept independent of Celery so it's unit-testable
with a fake repository and a capturing enqueue callback.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from uuid import UUID

from croniter import croniter

from app.models.enums import RunStatus
from app.models.run import Run
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)


def is_due(cron_expr: str, now: datetime, window_seconds: float) -> bool:
    """True if a scheduled time for ``cron_expr`` falls in ``(now - window, now]``.

    The dispatcher runs every ``window_seconds``; firing when the most recent
    scheduled time is within the last window means each occurrence triggers once.
    """
    if not croniter.is_valid(cron_expr):
        logger.warning("invalid cron expression: %r", cron_expr)
        return False
    previous = croniter(cron_expr, now).get_prev(datetime)
    return 0 <= (now - previous).total_seconds() < window_seconds


def due_workflows(
    workflows: Sequence[Workflow], now: datetime, window_seconds: float
) -> list[Workflow]:
    return [
        wf for wf in workflows if wf.schedule_cron and is_due(wf.schedule_cron, now, window_seconds)
    ]


async def dispatch_due(
    *,
    list_scheduled: Callable[[], Awaitable[Sequence[Workflow]]],
    create_run: Callable[[Run], Awaitable[Run]],
    enqueue: Callable[[str], None],
    now: datetime,
    window_seconds: float,
) -> list[UUID]:
    """Create a pending run for each due workflow and enqueue its execution.

    Returns the ids of the runs created. Dependencies are passed in so this can be
    driven by the real repository/Celery in production and fakes in tests.
    """
    scheduled = await list_scheduled()
    run_ids: list[UUID] = []
    for wf in due_workflows(scheduled, now, window_seconds):
        run = await create_run(Run(workflow_id=wf.id, status=RunStatus.pending))
        enqueue(str(run.id))
        run_ids.append(run.id)
        logger.info("scheduled workflow %s -> run %s", wf.id, run.id)
    return run_ids

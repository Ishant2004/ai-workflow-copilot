"""Worker-free scheduling.

`POST /api/scheduler/tick` runs the same "find due scheduled workflows and execute
them" logic the Celery Beat dispatcher would — but inline, driven by an external
cron (cron-job.org, UptimeRobot, GitHub Actions) instead of a paid worker. Protected
by a shared secret so only your scheduler can trigger it.

Point a cron at it every N seconds and pass ``window_seconds=N`` so each scheduled
occurrence fires exactly once. Scheduled runs execute unattended (no review gate).
"""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.config import Settings
from app.dependencies import (
    get_document_repo,
    get_embedder_dep,
    get_executor_dep,
    get_settings_dep,
    get_workflow_repo,
)
from app.execution.executor import WorkflowExecutor
from app.rag.embeddings import Embedder
from app.rag.retriever import DocumentRetriever
from app.repositories.documents import DocumentRepository
from app.repositories.workflows import WorkflowRepository
from app.worker.scheduling import due_workflows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

_TOKEN_HEADER = "X-Scheduler-Token"


class TickResult(BaseModel):
    dispatched: list[str]  # run ids created this tick
    count: int
    window_seconds: float


@router.post("/tick", response_model=TickResult)
async def tick(
    request: Request,
    window_seconds: float | None = Query(default=None, ge=1),
    repo: WorkflowRepository = Depends(get_workflow_repo),
    executor: WorkflowExecutor = Depends(get_executor_dep),
    settings: Settings = Depends(get_settings_dep),
    document_repo: DocumentRepository = Depends(get_document_repo),
    embedder: Embedder = Depends(get_embedder_dep),
) -> TickResult:
    token = settings.scheduler_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler is disabled (set SCHEDULER_TOKEN).",
        )
    provided = request.headers.get(_TOKEN_HEADER) or ""
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    window = window_seconds or settings.scheduler_tick_window_seconds
    scheduled = await repo.list_scheduled()
    due = due_workflows(scheduled, datetime.now(UTC), window)

    # Scheduled runs are unattended, so they run without the review gate.
    retriever = DocumentRetriever(document_repo, embedder)
    dispatched: list[str] = []
    for workflow in due:
        run = await executor.run(workflow, require_review=False, retriever=retriever)
        saved = await repo.create_run(run)
        dispatched.append(str(saved.id))
        logger.info("scheduler tick dispatched workflow %s -> run %s", workflow.id, saved.id)

    return TickResult(dispatched=dispatched, count=len(dispatched), window_seconds=window)

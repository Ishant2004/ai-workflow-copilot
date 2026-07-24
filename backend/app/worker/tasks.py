"""Celery tasks: async run execution and scheduled dispatch.

Each task builds its own async DB session and executor (the worker is a separate
process from the API), runs the coroutine via ``asyncio.run``, and disposes the
engine. A short-lived engine (NullPool) keeps worker connection use bounded.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 - register models
from app.config import Settings, get_settings
from app.execution.executor import WorkflowExecutor
from app.rag.embeddings import get_embedder
from app.rag.retriever import DocumentRetriever
from app.repositories.documents import SqlAlchemyDocumentRepository
from app.repositories.workflows import SqlAlchemyWorkflowRepository
from app.tools import build_tool_registry
from app.worker.celery_app import celery_app
from app.worker.scheduling import dispatch_due

logger = logging.getLogger(__name__)


async def _with_session[T](settings: Settings, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for worker tasks")
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            return await fn(session)
    finally:
        await engine.dispose()


async def _execute_run(settings: Settings, run_id: UUID) -> None:
    async def _run(session: AsyncSession) -> None:
        repo = SqlAlchemyWorkflowRepository(session)
        run = await repo.get_run(run_id)
        if run is None:
            logger.warning("execute_run: run %s not found", run_id)
            return
        workflow = await repo.get(run.workflow_id)
        if workflow is None:
            logger.warning("execute_run: workflow for run %s not found", run_id)
            return
        executor = WorkflowExecutor(build_tool_registry(settings), settings.tool_timeout_seconds)
        retriever = DocumentRetriever(SqlAlchemyDocumentRepository(session), get_embedder(settings))
        await executor.execute_run(
            workflow, run, require_review=settings.require_review, retriever=retriever
        )
        await repo.save_run(run)

    await _with_session(settings, _run)


@celery_app.task(name="app.worker.tasks.execute_run")
def execute_run(run_id: str) -> None:
    asyncio.run(_execute_run(get_settings(), UUID(run_id)))


async def _dispatch_due_workflows(settings: Settings) -> list[str]:
    async def _dispatch(session: AsyncSession) -> list[str]:
        repo = SqlAlchemyWorkflowRepository(session)
        run_ids = await dispatch_due(
            list_scheduled=repo.list_scheduled,
            create_run=repo.create_run,
            enqueue=lambda rid: execute_run.delay(rid),
            now=datetime.now(UTC),
            window_seconds=settings.beat_dispatch_interval_seconds,
        )
        return [str(r) for r in run_ids]

    return await _with_session(settings, _dispatch)


@celery_app.task(name="app.worker.tasks.dispatch_due_workflows")
def dispatch_due_workflows() -> list[str]:
    return asyncio.run(_dispatch_due_workflows(get_settings()))

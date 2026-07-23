"""Integration tests for the SQLAlchemy workflow repository.

Requires a reachable Postgres (DATABASE_URL / TEST_DATABASE_URL). Auto-skips when
none is available, so the suite stays green locally; runs in Docker/CI.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from app.llm.schemas import PlannedStep, WorkflowPlan
from app.models.enums import StepType, WorkflowStatus
from app.schemas.workflow import StepIn
from app.services.workflows import workflow_from_plan

pytestmark = pytest.mark.integration

_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

_PLAN = WorkflowPlan(
    title="DB round-trip",
    summary="s",
    steps=[
        PlannedStep(
            type=StepType.web_search, name="Search", description="d", config={"query": "x"}
        ),
        PlannedStep(type=StepType.summarize, name="Summarize", description="d", config={}),
    ],
)


async def _crud_round_trip(db_url: str) -> None:
    import app.models  # noqa: F401 - register models
    from app.db.base import Base
    from app.repositories.workflows import SqlAlchemyWorkflowRepository
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            repo = SqlAlchemyWorkflowRepository(session)

            wf = await repo.create(workflow_from_plan(description="task", plan=_PLAN))
            assert wf.id is not None
            assert len(wf.steps) == 2

            fetched = await repo.get(wf.id)
            assert fetched is not None
            assert fetched.title == "DB round-trip"

            items, total = await repo.list(limit=10, offset=0)
            assert total == 1 and len(items) == 1

            updated = await repo.update(
                wf.id,
                title="Renamed",
                status=WorkflowStatus.active,
                steps=[StepIn(type=StepType.notify_slack, name="Notify")],
            )
            assert updated is not None
            assert updated.title == "Renamed"
            assert updated.status is WorkflowStatus.active
            assert len(updated.steps) == 1

            assert await repo.list_runs(wf.id) == []
            assert await repo.delete(wf.id) is True
            assert await repo.get(wf.id) is None
    finally:
        await engine.dispose()


def test_workflow_repository_crud_round_trip():
    if not _DB_URL:
        pytest.skip("no DATABASE_URL/TEST_DATABASE_URL configured")
    try:
        asyncio.run(_crud_round_trip(_DB_URL))
    except Exception as exc:  # noqa: BLE001
        # A connection/setup failure means no usable DB — skip rather than fail.
        if "connect" in str(exc).lower() or "could not translate" in str(exc).lower():
            pytest.skip(f"database not reachable: {exc}")
        raise

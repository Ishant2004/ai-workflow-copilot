"""Workflow persistence behind an interface.

Routes depend on the ``WorkflowRepository`` abstraction, not on SQLAlchemy
directly — so the API can be exercised in tests with an in-memory fake (no DB),
and the storage backend can change without touching route code.
"""

from __future__ import annotations

import abc
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import WorkflowStatus
from app.models.run import Run
from app.models.workflow import Workflow
from app.schemas.workflow import StepIn
from app.services.workflows import steps_from_input


class WorkflowRepository(abc.ABC):
    @abc.abstractmethod
    async def create(self, workflow: Workflow) -> Workflow: ...

    @abc.abstractmethod
    async def get(self, workflow_id: UUID) -> Workflow | None: ...

    @abc.abstractmethod
    async def list(self, *, limit: int, offset: int) -> tuple[list[Workflow], int]: ...

    @abc.abstractmethod
    async def update(
        self,
        workflow_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: WorkflowStatus | None = None,
        steps: list[StepIn] | None = None,
    ) -> Workflow | None: ...

    @abc.abstractmethod
    async def delete(self, workflow_id: UUID) -> bool: ...

    @abc.abstractmethod
    async def list_runs(self, workflow_id: UUID) -> list[Run] | None:
        """Runs for a workflow, or None if the workflow doesn't exist."""

    @abc.abstractmethod
    async def get_run(self, run_id: UUID) -> Run | None: ...


class SqlAlchemyWorkflowRepository(WorkflowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, workflow: Workflow) -> Workflow:
        self._session.add(workflow)
        await self._session.commit()
        # expire_on_commit=False keeps attributes loaded; steps were set in memory.
        return workflow

    async def get(self, workflow_id: UUID) -> Workflow | None:
        stmt = (
            select(Workflow).where(Workflow.id == workflow_id).options(selectinload(Workflow.steps))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list(self, *, limit: int, offset: int) -> tuple[list[Workflow], int]:
        total = (
            await self._session.execute(select(func.count()).select_from(Workflow))
        ).scalar_one()
        stmt = (
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .order_by(Workflow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def update(
        self,
        workflow_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: WorkflowStatus | None = None,
        steps: list[StepIn] | None = None,
    ) -> Workflow | None:
        workflow = await self.get(workflow_id)
        if workflow is None:
            return None
        if title is not None:
            workflow.title = title
        if description is not None:
            workflow.description = description
        if status is not None:
            workflow.status = status
        if steps is not None:
            # Replace the collection; cascade delete-orphan removes the old steps.
            workflow.steps = steps_from_input(steps)
        await self._session.commit()
        return await self.get(workflow_id)

    async def delete(self, workflow_id: UUID) -> bool:
        workflow = await self._session.get(Workflow, workflow_id)
        if workflow is None:
            return False
        await self._session.delete(workflow)
        await self._session.commit()
        return True

    async def list_runs(self, workflow_id: UUID) -> list[Run] | None:
        workflow = await self._session.get(Workflow, workflow_id)
        if workflow is None:
            return None
        stmt = (
            select(Run)
            .where(Run.workflow_id == workflow_id)
            .options(selectinload(Run.step_results))
            .order_by(Run.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_run(self, run_id: UUID) -> Run | None:
        stmt = select(Run).where(Run.id == run_id).options(selectinload(Run.step_results))
        return (await self._session.execute(stmt)).scalar_one_or_none()

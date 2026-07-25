"""Feedback persistence behind an interface.

Same pattern as the workflow/document repositories: routes depend on the
abstraction so the API can be tested with an in-memory fake, and the store can
change without touching route code. Beyond plain CRUD, this repo exposes
``recent_examples`` — the read side of the feedback loop, returning positively-rated
suggestions as planner exemplars.
"""

from __future__ import annotations

import abc
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.schemas import PlanExample, WorkflowPlan
from app.models.enums import FeedbackRating
from app.models.feedback import Feedback


class FeedbackRepository(abc.ABC):
    @abc.abstractmethod
    async def create(self, feedback: Feedback) -> Feedback: ...

    @abc.abstractmethod
    async def list_for_workflow(self, workflow_id: UUID) -> list[Feedback]: ...

    @abc.abstractmethod
    async def recent_examples(self, limit: int) -> list[PlanExample]:
        """Most recent positively-rated suggestions, newest first, as exemplars."""


def _to_example(feedback: Feedback) -> PlanExample:
    return PlanExample(
        task_description=feedback.task_description,
        plan=WorkflowPlan.model_validate(feedback.plan),
    )


class SqlAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, feedback: Feedback) -> Feedback:
        self._session.add(feedback)
        await self._session.commit()
        return feedback

    async def list_for_workflow(self, workflow_id: UUID) -> list[Feedback]:
        stmt = (
            select(Feedback)
            .where(Feedback.workflow_id == workflow_id)
            .order_by(Feedback.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def recent_examples(self, limit: int) -> list[PlanExample]:
        if limit <= 0:
            return []
        stmt = (
            select(Feedback)
            .where(Feedback.rating == FeedbackRating.positive)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_example(row) for row in rows]

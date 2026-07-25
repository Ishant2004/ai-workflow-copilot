"""Feedback model — the raw signal behind the suggestion-improvement loop.

Each row captures a user's verdict on a workflow the planner generated. A
self-contained snapshot of the task + plan is stored alongside the rating so a
positively-rated suggestion remains a usable planning exemplar even if the source
workflow is later edited or deleted (``workflow_id`` is set null on delete rather
than cascading the feedback away).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import FeedbackRating

if TYPE_CHECKING:
    from app.models.workflow import Workflow


class Feedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    # Kept for traceability; nulled (not cascaded) if the workflow is deleted so
    # the snapshot survives as a learning example.
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), index=True, nullable=True
    )
    rating: Mapped[FeedbackRating] = mapped_column(nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Self-contained snapshot of the suggestion this feedback is about.
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)

    workflow: Mapped[Workflow | None] = relationship()

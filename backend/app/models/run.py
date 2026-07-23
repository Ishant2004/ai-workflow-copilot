"""Run and StepResult models.

A **Run** is one execution of a workflow. A **StepResult** records the outcome of a
single step within that run. Everything is recorded so runs can be listed (history),
retried (idempotency), and measured (observability) — all scalability concerns.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RunStatus, StepResultStatus

if TYPE_CHECKING:
    from app.models.workflow import Step, Workflow


class Run(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "runs"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(default=RunStatus.pending, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[Workflow] = relationship(back_populates="runs")
    step_results: Mapped[list[StepResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="StepResult.created_at",
    )


class StepResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "step_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("steps.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[StepResultStatus] = mapped_column(
        default=StepResultStatus.pending, nullable=False
    )
    # Structured output produced by the step (e.g. search hits, summary text).
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    run: Mapped[Run] = relationship(back_populates="step_results")
    step: Mapped[Step] = relationship()

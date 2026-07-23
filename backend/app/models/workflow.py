"""Workflow and Step models.

A **Workflow** is a user's goal (plain-English intent) plus its structured plan.
A **Step** is one typed, ordered unit of work within that plan.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import StepType, WorkflowStatus

if TYPE_CHECKING:
    from app.models.run import Run


class Workflow(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflows"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # The original plain-English task the user described.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(
        default=WorkflowStatus.draft, nullable=False, index=True
    )

    steps: Mapped[list[Step]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="Step.order_index",
    )
    runs: Mapped[list[Run]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class Step(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "steps"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Execution order within the workflow (0-based).
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[StepType] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Tool parameters (e.g. search query, recipient). Schema varies by step type.
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    workflow: Mapped[Workflow] = relationship(back_populates="steps")

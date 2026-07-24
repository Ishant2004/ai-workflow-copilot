"""API request/response schemas for workflows and runs.

Kept separate from the ORM models: these are the stable public contract, and
`from_attributes` lets them serialize ORM instances directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.schemas import WorkflowPlan
from app.models.enums import RunStatus, StepResultStatus, StepType, WorkflowStatus

# --- Steps ---


class StepIn(BaseModel):
    type: StepType
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_index: int
    type: StepType
    name: str
    description: str | None = None
    config: dict[str, Any]


# --- Workflows ---


class WorkflowCreate(BaseModel):
    task_description: str = Field(min_length=1, max_length=4000)
    # Optionally persist an already-previewed plan (avoids a second LLM call).
    plan: WorkflowPlan | None = None


class WorkflowUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    status: WorkflowStatus | None = None
    # When provided, fully replaces the workflow's steps (order = list order).
    steps: list[StepIn] | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    steps: list[StepOut]


class WorkflowList(BaseModel):
    items: list[WorkflowOut]
    total: int
    limit: int
    offset: int


# --- Runs (history; execution lands in later steps) ---


class StepResultUpdate(BaseModel):
    """Edit a step's output during review (before side-effecting steps run)."""

    output: dict[str, Any]


class StepResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    status: StepResultStatus
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    created_at: datetime
    step_results: list[StepResultOut]

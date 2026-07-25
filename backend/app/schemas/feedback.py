"""API request/response schemas for workflow feedback (Step 18)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FeedbackRating


class FeedbackCreate(BaseModel):
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID | None = None
    rating: FeedbackRating
    comment: str | None = None
    created_at: datetime

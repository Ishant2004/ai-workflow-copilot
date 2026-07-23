"""Planner endpoints.

Preview turns a plain-English task into a structured workflow plan without
persisting anything — persistence and CRUD land in Step 6.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_planner_dep
from app.llm import Planner, PlannerError, WorkflowPlan

router = APIRouter(prefix="/api/planner", tags=["planner"])


class PlanRequest(BaseModel):
    task_description: str = Field(min_length=1, max_length=4000)


@router.post("/preview", response_model=WorkflowPlan)
async def preview_plan(
    body: PlanRequest,
    planner: Planner = Depends(get_planner_dep),
) -> WorkflowPlan:
    """Generate a structured workflow plan from a task description (no persistence)."""
    try:
        return await planner.plan(body.task_description)
    except PlannerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

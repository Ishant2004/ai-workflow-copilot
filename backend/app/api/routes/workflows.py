"""Workflow CRUD + run-history endpoints.

Create generates a plan from the task description (or persists a supplied,
already-previewed plan), then stores it as a Workflow + ordered Steps. Run
endpoints are read-only history for now; execution lands in later steps.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings
from app.dependencies import get_planner_dep, get_settings_dep, get_workflow_repo
from app.llm import Planner, PlannerError
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import (
    RunOut,
    WorkflowCreate,
    WorkflowList,
    WorkflowOut,
    WorkflowUpdate,
)
from app.services.workflows import workflow_from_plan

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    repo: WorkflowRepository = Depends(get_workflow_repo),
    planner: Planner = Depends(get_planner_dep),
) -> WorkflowOut:
    plan = body.plan
    if plan is None:
        try:
            plan = await planner.plan(body.task_description)
        except PlannerError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    workflow = await repo.create(workflow_from_plan(description=body.task_description, plan=plan))
    return WorkflowOut.model_validate(workflow)


@router.get("", response_model=WorkflowList)
async def list_workflows(
    repo: WorkflowRepository = Depends(get_workflow_repo),
    settings: Settings = Depends(get_settings_dep),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> WorkflowList:
    # Clamp page size to the configured maximum (no magic numbers).
    effective_limit = min(limit or settings.api_default_page_size, settings.api_max_page_size)
    items, total = await repo.list(limit=effective_limit, offset=offset)
    return WorkflowList(
        items=[WorkflowOut.model_validate(w) for w in items],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowOut:
    workflow = await repo.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowOut.model_validate(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdate,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowOut:
    workflow = await repo.update(
        workflow_id,
        title=body.title,
        description=body.description,
        status=body.status,
        steps=body.steps,
    )
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowOut.model_validate(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> None:
    if not await repo.delete(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")


@router.get("/{workflow_id}/runs", response_model=list[RunOut])
async def list_workflow_runs(
    workflow_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> list[RunOut]:
    runs = await repo.list_runs(workflow_id)
    if runs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return [RunOut.model_validate(r) for r in runs]

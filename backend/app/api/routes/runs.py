"""Run detail endpoint (read-only history)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_workflow_repo
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import RunOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> RunOut:
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunOut.model_validate(run)

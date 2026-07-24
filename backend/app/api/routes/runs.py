"""Run endpoints — read history + the human-in-the-loop review actions.

A run pauses at ``awaiting_review`` before side-effecting steps. From there the
user can **edit** a produced result, **approve** (resume and run the remaining
steps), or **reject** (cancel without side effects).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_executor_dep, get_workflow_repo
from app.execution.executor import WorkflowExecutor
from app.models.enums import RunStatus
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import RunOut, StepResultUpdate

router = APIRouter(prefix="/api/runs", tags=["runs"])


async def _get_reviewable_run(run_id: UUID, repo: WorkflowRepository):
    """Fetch a run and ensure it's awaiting review (404 / 409 otherwise)."""
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status is not RunStatus.awaiting_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is not awaiting review (status: {run.status.value}).",
        )
    return run


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> RunOut:
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunOut.model_validate(run)


@router.patch("/{run_id}/steps/{step_result_id}", response_model=RunOut)
async def edit_step_result(
    run_id: UUID,
    step_result_id: UUID,
    body: StepResultUpdate,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> RunOut:
    """Edit a produced step's output before approving (e.g. tweak the summary)."""
    run = await _get_reviewable_run(run_id, repo)
    result = next((r for r in run.step_results if r.id == step_result_id), None)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step result not found")
    result.output = body.output
    saved = await repo.save_run(run)
    return RunOut.model_validate(saved)


@router.post("/{run_id}/approve", response_model=RunOut)
async def approve_run(
    run_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
    executor: WorkflowExecutor = Depends(get_executor_dep),
) -> RunOut:
    """Approve a paused run: execute the remaining (side-effecting) steps."""
    run = await _get_reviewable_run(run_id, repo)
    workflow = await repo.get(run.workflow_id)
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    await executor.resume(workflow, run)
    saved = await repo.save_run(run)
    return RunOut.model_validate(saved)


@router.post("/{run_id}/reject", response_model=RunOut)
async def reject_run(
    run_id: UUID,
    repo: WorkflowRepository = Depends(get_workflow_repo),
) -> RunOut:
    """Reject a paused run: cancel without running side-effecting steps."""
    run = await _get_reviewable_run(run_id, repo)
    run.status = RunStatus.rejected
    run.finished_at = datetime.now(UTC)
    saved = await repo.save_run(run)
    return RunOut.model_validate(saved)

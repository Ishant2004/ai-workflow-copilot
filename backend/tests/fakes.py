"""In-memory WorkflowRepository for testing routes without a database."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.models.enums import WorkflowStatus
from app.models.run import Run
from app.models.workflow import Step, Workflow
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import StepIn
from app.services.workflows import steps_from_input


def _stamp_step(step: Step) -> Step:
    now = datetime.now(UTC)
    step.id = uuid4()
    step.created_at = now
    step.updated_at = now
    return step


class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self) -> None:
        self._workflows: dict[UUID, Workflow] = {}
        self._runs: dict[UUID, Run] = {}

    async def create(self, workflow: Workflow) -> Workflow:
        now = datetime.now(UTC)
        workflow.id = uuid4()
        workflow.created_at = now
        workflow.updated_at = now
        for step in workflow.steps:
            step.workflow_id = workflow.id
            _stamp_step(step)
        self._workflows[workflow.id] = workflow
        return workflow

    async def get(self, workflow_id: UUID) -> Workflow | None:
        return self._workflows.get(workflow_id)

    async def list(self, *, limit: int, offset: int) -> tuple[list[Workflow], int]:
        ordered = sorted(self._workflows.values(), key=lambda w: w.created_at, reverse=True)
        return ordered[offset : offset + limit], len(ordered)

    async def update(
        self,
        workflow_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: WorkflowStatus | None = None,
        steps: list[StepIn] | None = None,
    ) -> Workflow | None:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return None
        if title is not None:
            workflow.title = title
        if description is not None:
            workflow.description = description
        if status is not None:
            workflow.status = status
        if steps is not None:
            new_steps = steps_from_input(steps)
            for step in new_steps:
                step.workflow_id = workflow.id
                _stamp_step(step)
            workflow.steps = new_steps
        workflow.updated_at = datetime.now(UTC)
        return workflow

    async def delete(self, workflow_id: UUID) -> bool:
        return self._workflows.pop(workflow_id, None) is not None

    async def create_run(self, run: Run) -> Run:
        now = datetime.now(UTC)
        run.id = uuid4()
        run.created_at = now
        run.updated_at = now
        for result in run.step_results:
            result.id = uuid4()
            result.run_id = run.id
            result.created_at = now
            result.updated_at = now
        self._runs[run.id] = run
        return run

    async def save_run(self, run: Run) -> Run:
        now = datetime.now(UTC)
        # Stamp any newly appended step results (from resume).
        for result in run.step_results:
            if result.id is None:
                result.id = uuid4()
                result.run_id = run.id
                result.created_at = now
                result.updated_at = now
        run.updated_at = now
        self._runs[run.id] = run
        return run

    async def list_runs(self, workflow_id: UUID) -> list[Run] | None:
        if workflow_id not in self._workflows:
            return None
        runs = [r for r in self._runs.values() if r.workflow_id == workflow_id]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    async def get_run(self, run_id: UUID) -> Run | None:
        return self._runs.get(run_id)

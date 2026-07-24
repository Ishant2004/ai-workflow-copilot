"""In-memory repositories for testing routes without a database."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.models.document import Document, DocumentChunk
from app.models.enums import WorkflowStatus
from app.models.run import Run
from app.models.workflow import Step, Workflow
from app.repositories.documents import DocumentRepository
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import WorkflowUpdate
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

    async def update(self, workflow_id: UUID, patch: WorkflowUpdate) -> Workflow | None:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return None
        if patch.title is not None:
            workflow.title = patch.title
        if patch.description is not None:
            workflow.description = patch.description
        if patch.status is not None:
            workflow.status = patch.status
        if patch.schedule_cron is not None:
            workflow.schedule_cron = patch.schedule_cron
        if patch.steps is not None:
            new_steps = steps_from_input(patch.steps)
            for step in new_steps:
                step.workflow_id = workflow.id
                _stamp_step(step)
            workflow.steps = new_steps
        workflow.updated_at = datetime.now(UTC)
        return workflow

    async def delete(self, workflow_id: UUID) -> bool:
        return self._workflows.pop(workflow_id, None) is not None

    async def list_scheduled(self) -> list[Workflow]:
        return [
            w
            for w in self._workflows.values()
            if w.status is WorkflowStatus.active and w.schedule_cron
        ]

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


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    return 1.0 - dot  # embeddings are unit-normalized, so dot == cosine similarity


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}

    async def create(self, document: Document) -> Document:
        now = datetime.now(UTC)
        document.id = uuid4()
        document.created_at = now
        document.updated_at = now
        for chunk in document.chunks:
            chunk.id = uuid4()
            chunk.document_id = document.id
            chunk.created_at = now
            chunk.updated_at = now
        self._documents[document.id] = document
        return document

    async def get(self, document_id: UUID) -> Document | None:
        return self._documents.get(document_id)

    async def list(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        ordered = sorted(self._documents.values(), key=lambda d: d.created_at, reverse=True)
        return ordered[offset : offset + limit], len(ordered)

    async def delete(self, document_id: UUID) -> bool:
        return self._documents.pop(document_id, None) is not None

    async def search(self, embedding: list[float], top_k: int) -> list[tuple[DocumentChunk, float]]:
        scored = [
            (chunk, _cosine_distance(embedding, chunk.embedding))
            for doc in self._documents.values()
            for chunk in doc.chunks
        ]
        scored.sort(key=lambda pair: pair[1])
        return scored[:top_k]

"""RAG grounding in workflows: retrieve tool, DocumentRetriever, executor wiring."""

import asyncio
from uuid import uuid4

import pytest
from app.config import Settings
from app.execution.executor import WorkflowExecutor
from app.models.enums import RunStatus, StepResultStatus, StepType
from app.models.workflow import Step, Workflow
from app.rag.embeddings import HashingEmbedder
from app.rag.retriever import DocumentRetriever, Retriever
from app.rag.service import ChunkingConfig, ingest_document
from app.tools import ToolError, build_tool_registry
from app.tools.retrieve import RETRIEVER_CONTEXT_KEY, RetrieveTool

from tests.fakes import InMemoryDocumentRepository

pytestmark = pytest.mark.unit


class _FakeRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int) -> list[dict]:
        return [{"content": f"chunk about {query}", "score": 0.9, "document_id": "d"}][:top_k]


def _step(step_type: StepType, **config) -> Step:
    return Step(order_index=0, type=step_type, name=step_type.value, config=config)


# --- retrieve tool ---


def test_retrieve_tool_uses_context_retriever():
    tool = RetrieveTool(default_top_k=5)
    ctx = {RETRIEVER_CONTEXT_KEY: _FakeRetriever()}
    out = asyncio.run(tool.run(_step(StepType.retrieve, query="payment terms"), ctx))
    assert out["count"] == 1
    assert "payment terms" in out["chunks"][0]["content"]


def test_retrieve_tool_requires_query():
    with pytest.raises(ToolError):
        asyncio.run(
            RetrieveTool(5).run(_step(StepType.retrieve), {RETRIEVER_CONTEXT_KEY: _FakeRetriever()})
        )


def test_retrieve_tool_errors_without_retriever():
    with pytest.raises(ToolError):
        asyncio.run(RetrieveTool(5).run(_step(StepType.retrieve, query="x"), {}))


# --- DocumentRetriever over the in-memory repo ---


def test_document_retriever_ranks_relevant_chunk_first():
    repo = InMemoryDocumentRepository()
    embedder = HashingEmbedder()

    async def go():
        for name, text in [
            ("invoice.txt", "Invoice payment terms are net 30 days."),
            ("weather.txt", "Mountain weather forecast is sunny."),
        ]:
            doc = ingest_document(
                filename=name,
                content_type="text/plain",
                data=text.encode(),
                embedder=embedder,
                chunking=ChunkingConfig(1000, 100),
            )
            await repo.create(doc)
        return await DocumentRetriever(repo, embedder).retrieve("invoice payment", 1)

    chunks = asyncio.run(go())
    assert len(chunks) == 1
    assert "Invoice payment" in chunks[0]["content"]


# --- executor grounding: retrieve → summarize ---


def test_executor_grounds_summary_on_retrieved_chunks():
    wf = Workflow(title="t", description="d")
    wf.id = uuid4()
    wf.steps = [
        Step(
            id=uuid4(), order_index=0, type=StepType.retrieve, name="r", config={"query": "invoice"}
        ),
        Step(id=uuid4(), order_index=1, type=StepType.summarize, name="s", config={}),
    ]
    executor = WorkflowExecutor(build_tool_registry(Settings(tools_provider="fake")), 30.0)
    run = asyncio.run(executor.run(wf, require_review=False, retriever=_FakeRetriever()))

    assert run.status is RunStatus.succeeded
    assert run.step_results[0].status is StepResultStatus.succeeded
    # summarize consumed the retrieved chunk
    assert run.step_results[1].output["source_count"] >= 1
    assert "invoice" in run.step_results[1].output["summary"]

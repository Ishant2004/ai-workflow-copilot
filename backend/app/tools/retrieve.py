"""Retrieve tool — RAG grounding step.

Pulls the chunks most relevant to the step's query from uploaded documents. The
retriever is supplied per run via the execution context (reserved key
``RETRIEVER_CONTEXT_KEY``) so this app-scoped tool reuses the run's DB session
instead of opening its own.
"""

from __future__ import annotations

from app.models.workflow import Step
from app.rag.retriever import Retriever
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput

# Reserved (non-serialized) context key carrying the per-run Retriever.
RETRIEVER_CONTEXT_KEY = "_retriever"


class RetrieveTool(Tool):
    def __init__(self, default_top_k: int) -> None:
        self._default_top_k = default_top_k

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        query = str(step.config.get("query") or "").strip()
        if not query:
            raise ToolError("retrieve requires a 'query' in the step config")

        retriever = context.get(RETRIEVER_CONTEXT_KEY)
        if not isinstance(retriever, Retriever):
            raise ToolError("retrieval is not available for this run")

        top_k = int(step.config.get("top_k") or self._default_top_k)
        chunks = await retriever.retrieve(query, top_k)
        return {"query": query, "count": len(chunks), "chunks": chunks}

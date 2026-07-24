"""Document retriever — the query→chunks capability used to ground workflows.

Bridges the (request/worker-scoped) document repository and the embedder into a
simple ``retrieve(query, top_k)`` call. Built per run and threaded into the
executor's context so the ``retrieve`` tool can pull relevant chunks — reusing the
same DB session rather than opening its own.
"""

from __future__ import annotations

import abc
from typing import Any

from app.rag.embeddings import Embedder
from app.rag.service import SupportsSearch, search_documents


class Retriever(abc.ABC):
    @abc.abstractmethod
    async def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Return relevant chunks as JSON-serializable dicts (highest score first)."""


class DocumentRetriever(Retriever):
    def __init__(self, repo: SupportsSearch, embedder: Embedder) -> None:
        self._repo = repo
        self._embedder = embedder

    async def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        hits = await search_documents(
            repo=self._repo, embedder=self._embedder, query=query, top_k=top_k
        )
        return [
            {
                "document_id": str(hit.chunk.document_id),
                "chunk_id": str(hit.chunk.id),
                "content": hit.chunk.content,
                "score": hit.score,
            }
            for hit in hits
        ]

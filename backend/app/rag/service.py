"""RAG ingest + search orchestration (DB-free where possible).

``ingest_document`` turns raw bytes into a transient Document + embedded chunks
(the repository persists it). ``search_documents`` embeds a query and delegates the
vector similarity search to the repository, converting distance to a 0–1 score.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from app.models.document import Document, DocumentChunk
from app.rag.chunking import chunk_text
from app.rag.embeddings import Embedder
from app.rag.extract import extract_text


class SupportsSearch(Protocol):
    async def search(
        self, embedding: list[float], top_k: int
    ) -> list[tuple[DocumentChunk, float]]: ...


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size: int
    overlap: int


@dataclass
class ChunkHit:
    chunk: DocumentChunk
    score: float  # cosine similarity in [0, 1] (higher = more relevant)


def ingest_document(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    embedder: Embedder,
    chunking: ChunkingConfig,
) -> Document:
    text = extract_text(filename, content_type, data)
    chunks = chunk_text(text, chunk_size=chunking.chunk_size, overlap=chunking.overlap)
    embeddings = embedder.embed(chunks) if chunks else []
    document = Document(filename=filename, content_type=content_type, size_bytes=len(data))
    document.chunks = [
        DocumentChunk(chunk_index=i, content=content, embedding=embedding)
        for i, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    ]
    return document


async def search_documents(
    *, repo: SupportsSearch, embedder: Embedder, query: str, top_k: int
) -> list[ChunkHit]:
    # Off the event loop: real embedders make a network call per query.
    query_vec = await asyncio.to_thread(embedder.embed_one, query)
    hits = await repo.search(query_vec, top_k)
    # pgvector returns cosine *distance* (0 = identical); similarity = 1 - distance.
    return [ChunkHit(chunk=chunk, score=1.0 - distance) for chunk, distance in hits]

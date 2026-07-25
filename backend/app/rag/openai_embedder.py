"""OpenAI-backed embedder.

Uses ``text-embedding-3-small`` with the ``dimensions`` parameter pinned to
``EMBEDDING_DIM``, so real semantic vectors fit the existing pgvector column with no
migration. Anthropic has no embeddings API, so RAG uses a separate provider here.

Calls the REST endpoint directly with httpx (already a dependency) to avoid pulling
in the OpenAI SDK. The ``Embedder`` interface is synchronous; embedding is a short,
low-frequency operation (ingest + one call per query), so a blocking request is
acceptable — see docs/scalability.md for the async-batching upgrade path.
"""

from __future__ import annotations

import logging
import math

import httpx

from app.rag.embeddings import EMBEDDING_DIM, Embedder

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/embeddings"


def _normalize(vec: list[float]) -> list[float]:
    # Reduced-dimension embeddings aren't guaranteed unit-length; normalize so cosine
    # search behaves consistently with the rest of the pipeline.
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = httpx.post(
                _OPENAI_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": texts, "dimensions": EMBEDDING_DIM},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("embedding request failed: %s", exc)
            raise RuntimeError(f"embedding request failed: {exc}") from exc

        # Preserve input order (OpenAI returns items with an "index" field).
        items = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [_normalize(item["embedding"]) for item in items]

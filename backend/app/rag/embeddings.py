"""Embedding providers.

Isolated behind the ``Embedder`` interface so a real provider (Voyage/OpenAI/etc.)
can be swapped in via config without touching the ingest/search code. The default
``HashingEmbedder`` is deterministic and offline — a feature-hashing bag-of-words
that yields cosine similarity reflecting token overlap, so retrieval genuinely
works in dev and tests without any API key.

``EMBEDDING_DIM`` is a structural constant: it sizes the pgvector column, so any
real provider must produce vectors of this dimension (project the provider's output
if needed), and changing it requires a migration.
"""

from __future__ import annotations

import abc
import hashlib
import math
import re

from app.config import Settings

EMBEDDING_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(abc.ABC):
    @property
    @abc.abstractmethod
    def dim(self) -> int: ...

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class HashingEmbedder(Embedder):
    """Deterministic feature-hashing embedder (offline, no dependencies)."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode()).digest()  # noqa: S324 - non-crypto use
            bucket = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


def get_embedder(settings: Settings) -> Embedder:
    provider = settings.embedding_provider.lower()
    if provider == "fake":
        return HashingEmbedder()
    # Real providers (Voyage/OpenAI/...) plug in here, projecting to EMBEDDING_DIM.
    raise ValueError(f"unknown embedding provider: {settings.embedding_provider!r}")

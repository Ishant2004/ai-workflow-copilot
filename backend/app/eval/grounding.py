"""Grounding score — a cheap, deterministic anti-hallucination proxy.

Measures how much of a produced digest is *supported* by its source material: the
fraction of the digest's content words that also appear in the sources. A low score
means the text asserts content not present in what it was given — the classic signal
of a hallucination. Pure and offline, so it runs in CI with no API; the ``Evaluator``
interface lets an LLM-graded check replace it later without changing callers.
"""

from __future__ import annotations

import re

# Common words carry no factual content, so they neither help nor hurt grounding.
_STOPWORD_TEXT = """
    a an the of to and or for in on at by with from into over under this that these those
    is are was were be been being it its as we you they i he she them his her their our your
    summary findings reviewed accuracy completeness round for based no source material supplied
"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def content_tokens(text: str) -> list[str]:
    """Lowercase content words: drops stopwords and tokens shorter than 3 chars."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3 and t not in _STOPWORDS]


def grounding_score(text: str, sources: list[str]) -> float:
    """Fraction of ``text``'s content words supported by ``sources`` (0.0–1.0).

    - No content words in ``text`` → 1.0 (nothing is claimed, nothing to hallucinate).
    - Content words present but no sources → 0.0 (every claim is unsupported).
    """
    claimed = content_tokens(text)
    if not claimed:
        return 1.0
    supported_vocab = {tok for src in sources for tok in content_tokens(src)}
    if not supported_vocab:
        return 0.0
    supported = sum(1 for tok in claimed if tok in supported_vocab)
    return supported / len(claimed)

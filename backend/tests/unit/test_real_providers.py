"""Real integration providers — Tavily web search + OpenAI embeddings (httpx mocked)."""

import asyncio

import pytest
from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.rag.embeddings import EMBEDDING_DIM, HashingEmbedder, get_embedder
from app.rag.openai_embedder import OpenAIEmbedder
from app.tools import ToolError, build_tool_registry
from app.tools.search import TavilyWebSearchTool

pytestmark = pytest.mark.unit


def _step(**config) -> Step:
    return Step(order_index=0, type=StepType.web_search, name="search", config=config)


# --- Tavily web search ---


class _FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, resp):
        self._resp = resp

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json):
        self.sent = json
        return self._resp


def test_tavily_maps_results(monkeypatch):
    resp = _FakeResp(payload={"results": [{"title": "T", "url": "http://u", "content": "snippet"}]})
    monkeypatch.setattr("app.tools.search.httpx.AsyncClient", _FakeAsyncClient(resp))
    tool = TavilyWebSearchTool("key", max_results=3, timeout_seconds=5)
    out = asyncio.run(tool.run(_step(query="ai news"), {}))
    assert out["query"] == "ai news"
    assert out["count"] == 1
    assert out["results"][0] == {"title": "T", "url": "http://u", "snippet": "snippet"}


def test_tavily_requires_query():
    tool = TavilyWebSearchTool("key", max_results=3, timeout_seconds=5)
    with pytest.raises(ToolError) as exc:
        asyncio.run(tool.run(_step(), {}))
    assert exc.value.retryable is False


def test_tavily_maps_http_error(monkeypatch):
    resp = _FakeResp(status_code=401, text="bad key")
    monkeypatch.setattr("app.tools.search.httpx.AsyncClient", _FakeAsyncClient(resp))
    tool = TavilyWebSearchTool("key", max_results=3, timeout_seconds=5)
    with pytest.raises(ToolError) as exc:
        asyncio.run(tool.run(_step(query="x"), {}))
    assert exc.value.retryable is False  # 4xx won't fix on retry


# --- OpenAI embeddings ---


def test_openai_embedder_orders_and_normalizes(monkeypatch):
    # Returned out of order; must be restored by "index" and unit-normalized.
    payload = {
        "data": [{"index": 1, "embedding": [3.0, 4.0]}, {"index": 0, "embedding": [1.0, 0.0]}]
    }
    monkeypatch.setattr(
        "app.rag.openai_embedder.httpx.post", lambda *a, **k: _FakeResp(payload=payload)
    )
    monkeypatch.setattr(_FakeResp, "raise_for_status", lambda self: None, raising=False)
    out = OpenAIEmbedder("key", "text-embedding-3-small", 5).embed(["a", "b"])
    assert out[0] == [1.0, 0.0]
    assert out[1] == pytest.approx([0.6, 0.8])


def test_openai_embedder_empty_input():
    assert OpenAIEmbedder("key", "m", 5).embed([]) == []


def test_get_embedder_openai_without_key_falls_back():
    emb = get_embedder(Settings(embedding_provider="openai", openai_api_key=None))
    assert isinstance(emb, HashingEmbedder)


def test_get_embedder_openai_with_key():
    emb = get_embedder(Settings(embedding_provider="openai", openai_api_key="sk-test"))
    assert isinstance(emb, OpenAIEmbedder)
    assert emb.dim == EMBEDDING_DIM


# --- registry wiring ---


def test_registry_uses_tavily_when_live_and_keyed():
    reg = build_tool_registry(
        Settings(
            tools_provider="live",
            search_provider="tavily",
            tavily_api_key="tv-key",
            anthropic_api_key=None,
        )
    )
    assert isinstance(reg.get(StepType.web_search), TavilyWebSearchTool)


def test_registry_falls_back_to_fake_search_without_key():
    reg = build_tool_registry(Settings(tools_provider="live", search_provider="tavily"))
    assert not isinstance(reg.get(StepType.web_search), TavilyWebSearchTool)

"""Scrape tool tests — text extraction, SSRF guard, and downstream consumption."""

import asyncio

import pytest
from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools import ToolError, build_tool_registry
from app.tools.fake import FakeSummarizeTool
from app.tools.scrape import FakeScrapeTool, ScrapeTool, extract_text

pytestmark = pytest.mark.unit


def _step(**config) -> Step:
    return Step(order_index=0, type=StepType.scrape, name="scrape", config=config)


# --- text extraction ---


def test_extract_text_strips_tags_and_scripts():
    html = "<html><head><title>x</title></head><body><script>var a=1</script>"
    html += "<h1>Hello</h1><p>World of <b>text</b></p><style>.a{}</style></body></html>"
    out = extract_text(html, 1000)
    assert "Hello" in out and "World of" in out and "text" in out
    assert "var a" not in out and ".a{}" not in out


def test_extract_text_truncates():
    assert len(extract_text("<p>" + "a" * 100 + "</p>", 10)) == 10


# --- fake scrape ---


def test_fake_scrape_requires_url():
    with pytest.raises(ToolError) as exc:
        asyncio.run(FakeScrapeTool().run(_step(), {}))
    assert exc.value.retryable is False


def test_fake_scrape_returns_content():
    out = asyncio.run(FakeScrapeTool().run(_step(url="http://example.com"), {}))
    assert out["url"] == "http://example.com"
    assert out["content"] and out["chars"] == len(out["content"])


# --- real scrape: SSRF guard + fetch (httpx mocked) ---


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest",
    ],
)
def test_scrape_blocks_unsafe_urls(url):
    tool = ScrapeTool(timeout_seconds=5, max_chars=1000)
    with pytest.raises(ToolError) as exc:
        asyncio.run(tool.run(_step(url=url), {}))
    assert exc.value.retryable is False


class _FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, resp):
        self._resp = resp

    def __call__(self, *a, **k):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers):
        return self._resp


def test_scrape_fetches_and_extracts(monkeypatch):
    resp = _FakeResp(text="<html><body><h1>Real Page</h1></body></html>")
    monkeypatch.setattr("app.tools.scrape.httpx.AsyncClient", _FakeAsyncClient(resp))
    tool = ScrapeTool(timeout_seconds=5, max_chars=1000)
    out = asyncio.run(tool.run(_step(url="https://example.com/page"), {}))
    assert out["url"] == "https://example.com/page"
    assert "Real Page" in out["content"]


# --- registry wiring + downstream consumption ---


def test_registry_maps_scrape_to_fake_by_default():
    reg = build_tool_registry(Settings(tools_provider="fake"))
    assert isinstance(reg.get(StepType.scrape), FakeScrapeTool)


def test_registry_uses_real_scrape_when_live():
    reg = build_tool_registry(Settings(tools_provider="live", anthropic_api_key=None))
    assert isinstance(reg.get(StepType.scrape), ScrapeTool)


def test_summarize_grounds_on_scrape_output():
    context = {StepType.scrape.value: {"content": "battery recycling breakthrough"}}
    out = asyncio.run(
        FakeSummarizeTool().run(
            Step(order_index=1, type=StepType.summarize, name="sum", config={}), context
        )
    )
    assert out["source_count"] == 1
    assert "battery recycling" in out["summary"]

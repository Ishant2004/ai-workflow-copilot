"""Scrape tool — fetch a URL and extract its readable text.

`FakeScrapeTool` is the deterministic offline default; `ScrapeTool` does a real
HTTP fetch (selected under ``TOOLS_PROVIDER=live``). Text extraction uses the stdlib
HTML parser — no extra dependency — skipping script/style/nav noise.

Because the URL is user-supplied, `ScrapeTool` refuses non-HTTP(S) schemes and
obvious internal targets (loopback, private/link-local IPs, cloud metadata) as a
basic SSRF guard. Note: a public hostname that *resolves* to a private IP (DNS
rebinding) is not caught here — a production guard resolves DNS and re-checks the IP.
"""

from __future__ import annotations

import ipaddress
import logging
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput

logger = logging.getLogger(__name__)

_USER_AGENT = "WorkflowAICopilot/1.0 (+scrape)"
_SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "svg", "template"})


class _TextExtractor(HTMLParser):
    """Collect visible text, ignoring scripts/styles and other non-content tags."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def text(self) -> str:
        return "\n".join(self._parts)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ToolError("scrape url must be http(s)", retryable=False)
    host = (parsed.hostname or "").lower()
    if not host or host == "localhost" or host.endswith(".local"):
        raise ToolError("scrape url host is not allowed", retryable=False)
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # a hostname (not a literal IP) — allowed
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ToolError("scrape url host is not allowed", retryable=False)


def extract_text(html: str, max_chars: int) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()[:max_chars]


class FakeScrapeTool(Tool):
    """Deterministic offline scrape — echoes plausible page text for the URL."""

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        url = str(step.config.get("url") or "").strip()
        if not url:
            raise ToolError("scrape requires a 'url' in the step config", retryable=False)
        content = f"Simulated page content for {url}. This is placeholder text used offline."
        return {"url": url, "content": content, "chars": len(content)}


class ScrapeTool(Tool):
    def __init__(self, timeout_seconds: float, max_chars: int) -> None:
        self._timeout = timeout_seconds
        self._max_chars = max_chars

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        url = str(step.config.get("url") or "").strip()
        if not url:
            raise ToolError("scrape requires a 'url' in the step config", retryable=False)
        _validate_url(url)

        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
        except httpx.HTTPError as exc:
            raise ToolError(f"scrape request failed: {exc}") from exc
        if resp.status_code != httpx.codes.OK:
            raise ToolError(
                f"scrape returned {resp.status_code}", retryable=resp.status_code >= 500
            )

        content = extract_text(resp.text, self._max_chars)
        return {"url": url, "content": content, "chars": len(content)}

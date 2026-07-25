"""Live web-search tool — real results via the Tavily API.

Selected when ``TOOLS_PROVIDER=live`` and ``SEARCH_PROVIDER=tavily`` with a key.
Returns the same output shape as the fake search tool (``query`` / ``count`` /
``results[{title,url,snippet}]``) so downstream summarize/orchestrate steps consume
it unchanged. Tavily is LLM-oriented (concise, relevant snippets) and has a free tier.
"""

from __future__ import annotations

import logging

import httpx

from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class TavilyWebSearchTool(Tool):
    def __init__(self, api_key: str, max_results: int, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._max_results = max_results
        self._timeout = timeout_seconds

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        query = str(step.config.get("query") or "").strip()
        if not query:
            raise ToolError("web_search requires a 'query' in the step config", retryable=False)

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": self._max_results,
            "search_depth": "basic",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(_TAVILY_URL, json=payload)
        except httpx.HTTPError as exc:
            raise ToolError(f"web search request failed: {exc}") from exc
        if resp.status_code != httpx.codes.OK:
            # 4xx (bad key/quota) won't fix on retry; 5xx might.
            retryable = resp.status_code >= 500
            raise ToolError(
                f"web search returned {resp.status_code}: {resp.text[:200]}", retryable=retryable
            )

        data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
            for item in data.get("results", [])
        ]
        return {"query": query, "count": len(results), "results": results}

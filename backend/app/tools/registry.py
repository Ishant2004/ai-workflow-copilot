"""Tool registry — maps each StepType to a Tool implementation, per config.

`fake` (default) wires deterministic offline tools. `live` swaps in real
providers where they're configured (currently the Claude summarizer), falling
back to the fake for anything not yet available so a run still completes.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.models.enums import StepType
from app.tools.base import Tool
from app.tools.fake import FakeNotifyTool, FakeSummarizeTool, FakeWebSearchTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, tools: dict[StepType, Tool]) -> None:
        self._tools = tools

    def get(self, step_type: StepType) -> Tool:
        tool = self._tools.get(step_type)
        if tool is None:
            raise KeyError(f"no tool registered for step type {step_type.value!r}")
        return tool


def build_tool_registry(settings: Settings) -> ToolRegistry:
    web_search = FakeWebSearchTool(max_results=settings.search_max_results)
    summarize: Tool = FakeSummarizeTool()
    notify = FakeNotifyTool()

    if settings.tools_provider.lower() == "live":
        if settings.anthropic_api_key:
            from app.tools.summarize import ClaudeSummarizeTool  # noqa: PLC0415

            summarize = ClaudeSummarizeTool(settings)
        else:
            logger.warning(
                "TOOLS_PROVIDER=live but ANTHROPIC_API_KEY is unset; using the fake summarizer."
            )
        # A live web-search provider plugs in here once configured.

    return ToolRegistry(
        {
            StepType.web_search: web_search,
            StepType.scrape: web_search,  # reuse search behavior for the scrape stub
            StepType.summarize: summarize,
            StepType.notify_slack: notify,
            StepType.notify_email: notify,
        }
    )

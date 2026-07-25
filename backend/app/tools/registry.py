"""Tool registry — maps each StepType to a Tool implementation, per config.

`fake` (default) wires deterministic offline tools. `live` swaps in real
providers where they're configured (currently the Claude summarizer), falling
back to the fake for anything not yet available so a run still completes.
"""

from __future__ import annotations

import logging

from app.agents import get_orchestrator
from app.config import Settings
from app.models.enums import StepType
from app.tools.base import Tool
from app.tools.fake import FakeNotifyTool, FakeSummarizeTool, FakeWebSearchTool
from app.tools.orchestrate import OrchestrateTool
from app.tools.retrieve import RetrieveTool
from app.tools.scrape import FakeScrapeTool

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
    scrape: Tool = FakeScrapeTool()
    summarize: Tool = FakeSummarizeTool()
    notify_slack: Tool = FakeNotifyTool()
    notify_email: Tool = FakeNotifyTool()

    if settings.tools_provider.lower() == "live":
        from app.tools.scrape import ScrapeTool  # noqa: PLC0415

        scrape = ScrapeTool(settings.tool_timeout_seconds, settings.scrape_max_chars)

        if settings.anthropic_api_key:
            from app.tools.summarize import ClaudeSummarizeTool  # noqa: PLC0415

            summarize = ClaudeSummarizeTool(settings)
        else:
            logger.warning(
                "TOOLS_PROVIDER=live but ANTHROPIC_API_KEY is unset; using the fake summarizer."
            )

        if settings.search_provider.lower() == "tavily" and settings.tavily_api_key:
            from app.tools.search import TavilyWebSearchTool  # noqa: PLC0415

            web_search = TavilyWebSearchTool(
                settings.tavily_api_key,
                settings.search_max_results,
                settings.tool_timeout_seconds,
            )
        elif settings.search_provider.lower() == "tavily":
            logger.warning("SEARCH_PROVIDER=tavily but TAVILY_API_KEY is unset; using fake search.")

        if settings.slack_webhook_url:
            from app.tools.notify import LiveSlackNotifyTool  # noqa: PLC0415

            notify_slack = LiveSlackNotifyTool(
                settings.slack_webhook_url, settings.tool_timeout_seconds
            )
        else:
            logger.warning("SLACK_WEBHOOK_URL unset; using the simulated Slack notifier.")

        if settings.smtp_host and settings.email_from:
            from app.tools.notify import LiveEmailNotifyTool, SmtpConfig  # noqa: PLC0415

            notify_email = LiveEmailNotifyTool(
                SmtpConfig(
                    host=settings.smtp_host,
                    port=settings.smtp_port,
                    sender=settings.email_from,
                    user=settings.smtp_user,
                    password=settings.smtp_password,
                ),
                settings.tool_timeout_seconds,
            )
        else:
            logger.warning("SMTP not configured; using the simulated email notifier.")
        # A live web-search provider plugs in here once configured.

    # The orchestrator follows the same fake/live selection as the summarizer.
    orchestrate = OrchestrateTool(get_orchestrator(settings))

    return ToolRegistry(
        {
            StepType.web_search: web_search,
            StepType.scrape: scrape,
            StepType.retrieve: RetrieveTool(default_top_k=settings.rag_top_k),
            StepType.summarize: summarize,
            StepType.orchestrate: orchestrate,
            StepType.notify_slack: notify_slack,
            StepType.notify_email: notify_email,
        }
    )

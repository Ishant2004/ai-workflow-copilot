"""Planner selection from config.

Returns ``None`` (rather than raising) when the configured provider can't be
constructed — e.g. Anthropic selected but no API key. The app starts either way;
the planner endpoint returns 503 until a provider is available. This keeps local
dev and prod-shaped tests working without a key.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.llm.base import Planner
from app.llm.fake_planner import FakePlanner

logger = logging.getLogger(__name__)


def get_planner(settings: Settings) -> Planner | None:
    provider = settings.llm_provider.lower()

    if provider == "fake":
        return FakePlanner()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set; "
                "planner disabled. Set the key or use LLM_PROVIDER=fake."
            )
            return None
        # Imported lazily so the SDK isn't required when using the fake provider.
        from app.llm.anthropic_planner import AnthropicPlanner  # noqa: PLC0415

        return AnthropicPlanner(settings)

    logger.warning("unknown LLM_PROVIDER=%r; planner disabled", settings.llm_provider)
    return None

"""FastAPI dependencies.

Settings are read from ``app.state`` (populated by ``create_app``) rather than the
global cache, so each app instance — including per-test instances — uses exactly the
settings it was constructed with.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import Settings
from app.llm import Planner


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_planner_dep(request: Request) -> Planner:
    """Return the app's planner, or 503 if no provider is configured."""
    planner = request.app.state.planner
    if planner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Planner is not configured (set ANTHROPIC_API_KEY or LLM_PROVIDER=fake).",
        )
    return planner

"""FastAPI dependencies.

Settings are read from ``app.state`` (populated by ``create_app``) rather than the
global cache, so each app instance — including per-test instances — uses exactly the
settings it was constructed with.
"""

from __future__ import annotations

from fastapi import Request

from app.config import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings

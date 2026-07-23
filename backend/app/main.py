"""Application entrypoint.

Uses an application-factory (``create_app``) so the app is constructed fresh per
process — friendly to running multiple stateless Uvicorn workers/replicas, and to
tests that need an isolated instance. No global mutable state lives here.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.middleware import RequestIDMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
        # Startup hooks (DB/Redis pools) will attach here in later steps.
        yield
        logger.info("Shutting down %s", settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    # Order matters: request-id first so all downstream logs are correlated.
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": "/docs"}

    return app


app = create_app()

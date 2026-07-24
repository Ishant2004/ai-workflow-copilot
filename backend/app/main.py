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

from app.api.routes import documents, health, planner, runs, workflows
from app.config import Settings, get_settings
from app.db.session import create_engine_from_settings, create_session_factory
from app.execution.executor import WorkflowExecutor
from app.llm import get_planner
from app.logging_config import configure_logging
from app.middleware import RequestIDMiddleware
from app.rag.embeddings import get_embedder
from app.tools import build_tool_registry

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
        # Open the DB connection pool on startup, dispose it on shutdown.
        engine = None
        if settings.database_url:
            engine = create_engine_from_settings(settings)
            app.state.db_engine = engine
            app.state.session_factory = create_session_factory(engine)
            logger.info("Database pool initialized")
        else:
            app.state.db_engine = None
            app.state.session_factory = None
            logger.warning("DATABASE_URL not set — database features disabled")
        try:
            yield
        finally:
            if engine is not None:
                await engine.dispose()
                logger.info("Database pool disposed")
        logger.info("Shutting down %s", settings.app_name)

    # In production, don't expose the interactive docs / OpenAPI schema.
    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"
    openapi_url = None if settings.is_production else "/openapi.json"

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug and not settings.is_production,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Make this instance's settings available to routes via dependency injection.
    app.state.settings = settings
    # Build the planner once per app (None if no provider is available).
    app.state.planner = get_planner(settings)
    # Build the tool registry + executor once per app.
    app.state.executor = WorkflowExecutor(
        build_tool_registry(settings), settings.tool_timeout_seconds
    )
    # Build the embedder once per app (RAG).
    app.state.embedder = get_embedder(settings)

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
    app.include_router(planner.router)
    app.include_router(workflows.router)
    app.include_router(runs.router)
    app.include_router(documents.router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": docs_url or "disabled"}

    return app


app = create_app()

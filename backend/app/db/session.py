"""Async database engine and session management.

The connection pool is sized from config so that, across N replicas, total
connections stay under Postgres ``max_connections``:

    total ≈ replicas * (db_pool_size + db_max_overflow)

``pool_pre_ping`` transparently recycles connections dropped by the DB/LB, avoiding
errors after idle periods — important once we scale out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Build an async engine with pool parameters from config (no magic numbers)."""
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay usable after commit (common in async APIs).
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session.

    The session factory lives on ``app.state`` (set during lifespan startup), so each
    app instance uses its own engine/pool.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session

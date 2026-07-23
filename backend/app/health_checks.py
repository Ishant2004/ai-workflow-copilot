"""Dependency health checks used by the readiness probe.

Each check is bounded by a short timeout (from config) so a slow/hung dependency
can't block the probe — a replica reports "not ready" rather than hanging, and the
orchestrator stops routing traffic to it (backpressure over collapse). Checks run
concurrently.

Imports of the DB/cache drivers are lazy so the app (and unit tests) can run without
those libraries installed or those dependencies configured.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def check_postgres(database_url: str, timeout_seconds: float) -> None:
    """Raise if Postgres is unreachable. Uses psycopg (async)."""
    import psycopg  # noqa: PLC0415 - lazy import: optional driver

    # SQLAlchemy-style "+psycopg" suffix isn't valid for a raw libpq DSN.
    dsn = database_url.replace("+psycopg", "", 1)
    conn = await psycopg.AsyncConnection.connect(dsn, connect_timeout=int(timeout_seconds))
    try:
        await conn.execute("SELECT 1")
    finally:
        await conn.close()


async def check_redis(redis_url: str, timeout_seconds: float) -> None:
    """Raise if Redis is unreachable."""
    import redis.asyncio as redis  # noqa: PLC0415 - lazy import: optional driver

    client = redis.from_url(redis_url, socket_connect_timeout=timeout_seconds)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _run(name: str, coro, timeout_seconds: float) -> tuple[str, bool, str | None]:
    try:
        await asyncio.wait_for(coro, timeout=timeout_seconds)
        return name, True, None
    except Exception as exc:  # noqa: BLE001 - report any failure as "down"
        logger.warning("readiness check failed for %s: %s", name, exc)
        return name, False, str(exc)


async def run_readiness_checks(
    *,
    database_url: str | None,
    redis_url: str | None,
    timeout_seconds: float,
) -> tuple[bool, dict[str, str]]:
    """Run all configured dependency checks concurrently.

    Only dependencies that are *configured* are checked. Returns ``(ready, details)``
    where ``ready`` is False if any configured dependency is down.
    """
    tasks = []
    if database_url:
        tasks.append(
            _run("postgres", check_postgres(database_url, timeout_seconds), timeout_seconds)
        )
    if redis_url:
        tasks.append(_run("redis", check_redis(redis_url, timeout_seconds), timeout_seconds))

    if not tasks:
        return True, {}

    results = await asyncio.gather(*tasks)
    details = {name: ("ok" if ok else f"error: {err}") for name, ok, err in results}
    ready = all(ok for _, ok, _ in results)
    return ready, details

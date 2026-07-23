"""Readiness dependency-check logic tests (no real infra required)."""

import asyncio

import app.health_checks as hc
import pytest

pytestmark = pytest.mark.unit


TIMEOUT = 2.0


def test_no_deps_configured_is_ready():
    ready, details = asyncio.run(
        hc.run_readiness_checks(database_url=None, redis_url=None, timeout_seconds=TIMEOUT)
    )
    assert ready is True
    assert details == {}


def test_failing_dependency_reported_as_not_ready(monkeypatch):
    async def boom(_url, _timeout):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(hc, "check_postgres", boom)

    ready, details = asyncio.run(
        hc.run_readiness_checks(
            database_url="postgresql://x", redis_url=None, timeout_seconds=TIMEOUT
        )
    )
    assert ready is False
    assert "error" in details["postgres"]


def test_healthy_dependency_reported_ok(monkeypatch):
    async def ok(_url, _timeout):
        return None

    monkeypatch.setattr(hc, "check_postgres", ok)
    monkeypatch.setattr(hc, "check_redis", ok)

    ready, details = asyncio.run(
        hc.run_readiness_checks(
            database_url="postgresql://x",
            redis_url="redis://y",
            timeout_seconds=TIMEOUT,
        )
    )
    assert ready is True
    assert details == {"postgres": "ok", "redis": "ok"}

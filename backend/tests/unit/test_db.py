"""Engine/pool configuration tests (no connection is opened)."""

import asyncio

import pytest
from app.config import Settings
from app.db.session import create_engine_from_settings, create_session_factory

pytestmark = pytest.mark.unit

_FAKE_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def test_pool_sized_from_config():
    settings = Settings(
        database_url=_FAKE_URL,
        db_pool_size=7,
        db_max_overflow=3,
    )
    engine = create_engine_from_settings(settings)
    try:
        # Values come from config — no magic numbers in the engine module.
        assert engine.pool.size() == 7
        assert engine.pool._max_overflow == 3
    finally:
        asyncio.run(engine.dispose())


def test_missing_database_url_raises():
    with pytest.raises(RuntimeError):
        create_engine_from_settings(Settings(database_url=None))


def test_session_factory_builds():
    settings = Settings(database_url=_FAKE_URL)
    engine = create_engine_from_settings(settings)
    try:
        factory = create_session_factory(engine)
        assert factory is not None
    finally:
        asyncio.run(engine.dispose())

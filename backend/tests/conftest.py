"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Default (development) settings with no datastores configured."""
    return Settings(app_env="development", database_url=None, redis_url=None)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Test client for an app built from the given settings."""
    return TestClient(create_app(settings))


@pytest.fixture
def prod_client() -> TestClient:
    """Test client for an app built in production mode."""
    return TestClient(create_app(Settings(app_env="production")))

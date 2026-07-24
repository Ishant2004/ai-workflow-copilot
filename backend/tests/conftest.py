"""Shared test fixtures."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.dependencies import get_document_repo, get_workflow_repo
from app.main import create_app
from fastapi.testclient import TestClient

from tests.fakes import InMemoryDocumentRepository, InMemoryWorkflowRepository


@pytest.fixture
def settings() -> Settings:
    """Default (development) settings: no datastores, fake planner (offline)."""
    return Settings(
        app_env="development",
        database_url=None,
        redis_url=None,
        llm_provider="fake",
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Test client for an app built from the given settings."""
    return TestClient(create_app(settings))


@pytest.fixture
def prod_client() -> TestClient:
    """Test client for an app built in production mode."""
    return TestClient(create_app(Settings(app_env="production")))


@pytest.fixture
def workflow_repo() -> InMemoryWorkflowRepository:
    return InMemoryWorkflowRepository()


@pytest.fixture
def workflow_client(settings: Settings, workflow_repo: InMemoryWorkflowRepository) -> TestClient:
    """Client with the workflow repository overridden by an in-memory fake."""
    app = create_app(settings)
    app.dependency_overrides[get_workflow_repo] = lambda: workflow_repo
    return TestClient(app)


@pytest.fixture
def document_repo() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


@pytest.fixture
def document_client(settings: Settings, document_repo: InMemoryDocumentRepository) -> TestClient:
    """Client with the document repository overridden by an in-memory fake."""
    app = create_app(settings)
    app.dependency_overrides[get_document_repo] = lambda: document_repo
    return TestClient(app)

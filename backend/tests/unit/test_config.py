"""Config / environment-separation tests."""

import pytest
from app.config import Settings

pytestmark = pytest.mark.unit


def test_cors_origins_parsed_from_csv():
    s = Settings(cors_origins="http://a.com, http://b.com")
    assert s.cors_origins == ["http://a.com", "http://b.com"]


def test_development_flags():
    s = Settings(app_env="development")
    assert s.is_development is True
    assert s.is_production is False


def test_production_flags():
    s = Settings(app_env="production")
    assert s.is_production is True
    assert s.is_development is False


def test_root_reports_docs_enabled_in_dev(client):
    assert client.get("/").json()["docs"] == "/docs"


def test_docs_hidden_in_production(prod_client):
    """Interactive docs and OpenAPI schema are not exposed in production."""
    assert prod_client.get("/docs").status_code == 404
    assert prod_client.get("/openapi.json").status_code == 404
    assert prod_client.get("/").json()["docs"] == "disabled"

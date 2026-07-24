"""Application configuration.

12-factor config: everything comes from environment variables (or a local ``.env``
file for development). The same container image runs on a laptop or on ECS with
different replica counts — only the environment changes. This keeps services
stateless and horizontally scalable.

Environment separation
-----------------------
``APP_ENV`` (development | staging | production) selects an env-specific dotenv file
layered on top of the base ``.env``:

    .env                # shared / local defaults          (lowest priority)
    .env.<APP_ENV>      # per-environment overrides         (higher priority)
    real env vars       # injected by Docker/ECS/CI         (highest priority)

In production we don't ship a dotenv file at all — real environment variables are
injected by the platform.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _env_files() -> tuple[str, ...]:
    """Env files to load, lowest-priority first.

    ``APP_ENV`` is read from the raw environment so we know which env-specific file
    to layer on top of the base ``.env``.
    """
    app_env = os.getenv("APP_ENV", "development")
    return (".env", f".env.{app_env}")


class Settings(BaseSettings):
    """Typed application settings, loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "Workflow AI Copilot"
    log_level: str = "INFO"
    version: str = "0.1.0"
    debug: bool = False

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- CORS ---
    # Accepts a comma-separated string in the env; exposed as a list.
    # NoDecode: skip pydantic-settings' JSON decoding so our CSV validator runs.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Datastores (optional until configured; readiness probe checks them) ---
    database_url: str | None = None
    redis_url: str | None = None

    # --- Readiness probe ---
    # Per-dependency timeout so a slow/hung dependency can't block the probe.
    readiness_timeout_seconds: float = 2.0

    # --- Database connection pool (used from Step 4) ---
    # Sized per replica; keep (replicas * (pool + overflow)) under Postgres max_connections.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: float = 30.0
    db_pool_recycle_seconds: int = 1800

    # --- API pagination ---
    api_default_page_size: int = 20
    api_max_page_size: int = 100

    # --- LLM / planner (Step 5) ---
    # Provider is swappable behind an interface (see app/llm). "fake" needs no
    # network/key and is used for local dev and tests.
    llm_provider: str = "anthropic"  # anthropic | fake
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-8"
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # Cap concurrent in-flight LLM calls per process so a burst can't exhaust
    # the pool or blow past provider rate limits (see docs/scalability.md).
    llm_max_concurrency: int = 8

    # --- Tool execution (Step 9) ---
    # "fake" runs deterministic offline tools (dev/tests). "live" plugs in real
    # providers where configured (e.g. Claude summarizer), falling back to fake.
    tools_provider: str = "fake"  # fake | live
    tool_timeout_seconds: float = 30.0
    search_max_results: int = 5
    # Human-in-the-loop: pause a run before side-effecting steps (Slack/email)
    # so the user can approve/edit/reject first. Disable for fully-automated runs.
    require_review: bool = True

    # --- Output actions / notifications (Step 11) ---
    # Live Slack uses an incoming-webhook URL; live email uses SMTP. When unset,
    # the notify steps fall back to the simulated fake even under TOOLS_PROVIDER=live.
    slack_webhook_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read the environment once)."""
    return Settings()

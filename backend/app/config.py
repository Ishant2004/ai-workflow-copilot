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

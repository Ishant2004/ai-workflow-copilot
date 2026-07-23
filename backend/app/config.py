"""Application configuration.

12-factor config: everything comes from environment variables (or a local ``.env``
file for development). The same container image runs on a laptop or on ECS with
different replica counts — only the environment changes. This keeps services
stateless and horizontally scalable.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "Workflow AI Copilot"
    log_level: str = "INFO"
    version: str = "0.1.0"

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- CORS ---
    # Accepts a comma-separated string in the env; exposed as a list.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read the environment once)."""
    return Settings()

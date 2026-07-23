"""Health & probe endpoints.

Separate liveness and readiness endpoints so an orchestrator (ECS/Kubernetes) can
restart a hung replica (liveness) without routing traffic to a replica that isn't
ready yet (readiness). Readiness will later check downstream deps (DB, Redis).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Overall service health and basic identity."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        env=settings.app_env,
        version=settings.version,
    )


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Liveness: the process is up. Cheap, no downstream checks."""
    return {"status": "alive"}


@router.get("/health/ready")
def readiness() -> dict[str, str]:
    """Readiness: safe to receive traffic.

    Currently trivially ready; later steps add checks for Postgres and Redis so a
    replica only accepts traffic once its dependencies are reachable.
    """
    return {"status": "ready"}

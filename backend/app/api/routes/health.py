"""Health & probe endpoints.

Separate liveness and readiness endpoints so an orchestrator (ECS/Kubernetes) can
restart a hung replica (liveness) without routing traffic to a replica that isn't
ready yet (readiness). Readiness checks downstream deps (Postgres, Redis).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.config import Settings
from app.dependencies import get_settings_dep
from app.health_checks import run_readiness_checks

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings_dep)) -> HealthResponse:
    """Overall service health and basic identity."""
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
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, object]:
    """Readiness: safe to receive traffic.

    Checks each *configured* dependency (Postgres, Redis) concurrently with a short
    timeout. Returns 503 if any configured dependency is down so the load balancer
    stops routing traffic to this replica.
    """
    ready, checks = await run_readiness_checks(
        database_url=settings.database_url,
        redis_url=settings.redis_url,
    )
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}

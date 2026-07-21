"""Health, liveness, and readiness endpoints.

* ``/health`` — lightweight liveness signal (process is up).
* ``/live``   — Kubernetes-style liveness probe.
* ``/ready``  — readiness probe that verifies downstream dependencies.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.schemas.common import HealthComponent, HealthStatus
from app.services.health import collect_readiness

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus, summary="Liveness signal")
async def health() -> HealthStatus:
    """Return ``ok`` when the process is running."""
    return HealthStatus(
        status="ok",
        components=[HealthComponent(name="api", status="ok")],
    )


@router.get("/live", response_model=HealthStatus, summary="Liveness probe")
async def live() -> HealthStatus:
    """Kubernetes liveness probe — process-level only."""
    return HealthStatus(status="ok", components=[])


@router.get("/ready", response_model=HealthStatus, summary="Readiness probe")
async def ready(response: Response) -> HealthStatus:
    """Verify downstream dependencies and report aggregate readiness.

    Returns HTTP 503 when any required dependency is unavailable so orchestrators
    stop routing traffic until the service is fully ready.
    """
    result = await collect_readiness()
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result

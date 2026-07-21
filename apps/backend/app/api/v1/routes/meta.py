"""Service metadata endpoints (root and version)."""

from __future__ import annotations

from fastapi import APIRouter

from app.__version__ import __version__
from app.config import settings
from app.schemas.common import VersionInfo

router = APIRouter(tags=["meta"])


@router.get("/", summary="API root")
async def root() -> dict[str, str]:
    """Return a friendly root payload with links to docs."""
    return {
        "service": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@router.get("/version", response_model=VersionInfo, summary="Service version")
async def version() -> VersionInfo:
    """Return service identity and build metadata."""
    return VersionInfo(
        name=settings.app_name,
        version=__version__,
        environment=settings.environment.value,
    )

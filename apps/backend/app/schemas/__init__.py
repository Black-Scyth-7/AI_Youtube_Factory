"""Pydantic schema package."""

from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    HealthComponent,
    HealthStatus,
    VersionInfo,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthComponent",
    "HealthStatus",
    "VersionInfo",
]

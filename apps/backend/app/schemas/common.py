"""Shared API response schemas.

Provides a consistent envelope for errors and simple status payloads used across
all API versions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Machine-readable error body returned by the global exception handlers."""

    code: str = Field(description="Stable, machine-readable error identifier.")
    message: str = Field(description="Human-readable error description.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Optional structured context."
    )
    request_id: str | None = Field(
        default=None, description="Correlates the error with server logs."
    )


class ErrorResponse(BaseModel):
    """Top-level error envelope."""

    error: ErrorDetail


class HealthComponent(BaseModel):
    """Health of a single subsystem dependency."""

    name: str
    status: Literal["ok", "degraded", "down"]
    detail: str | None = None


class HealthStatus(BaseModel):
    """Aggregate readiness/liveness report."""

    status: Literal["ok", "degraded", "down"]
    components: list[HealthComponent] = Field(default_factory=list)


class VersionInfo(BaseModel):
    """Service identity and build metadata."""

    name: str
    version: str
    environment: str

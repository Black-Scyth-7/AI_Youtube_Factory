"""Structured application error types.

All domain and infrastructure errors derive from :class:`AppError`, which carries
an HTTP status, a stable machine-readable ``code``, and optional ``details``.
This lets the global handlers render a single, consistent error envelope.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all application-raised errors.

    Attributes:
        status_code: HTTP status to return.
        code: Stable, machine-readable identifier (e.g. ``not_found``).
        message: Human-readable description safe to surface to clients.
        details: Optional structured context (never includes secrets).
    """

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    """Requested resource does not exist."""

    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    """Request conflicts with the current state of a resource."""

    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current resource state."


class ValidationError(AppError):
    """Request failed domain-level validation."""

    status_code = 422
    code = "validation_error"
    message = "The request failed validation."


class UnauthorizedError(AppError):
    """Authentication is required or has failed."""

    status_code = 401
    code = "unauthorized"
    message = "Authentication is required."


class ForbiddenError(AppError):
    """Authenticated principal lacks permission."""

    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class ServiceUnavailableError(AppError):
    """A required downstream dependency is unavailable."""

    status_code = 503
    code = "service_unavailable"
    message = "A required service is currently unavailable."


class RateLimitError(AppError):
    """The caller exceeded a rate limit."""

    status_code = 429
    code = "rate_limited"
    message = "Too many requests."


class StorageError(AppError):
    """An object-storage operation failed."""

    status_code = 502
    code = "storage_error"
    message = "A storage operation failed."


class ExternalServiceError(AppError):
    """An upstream third-party service failed."""

    status_code = 502
    code = "external_service_error"
    message = "An external service request failed."


class WorkflowError(AppError):
    """A workflow definition or execution error."""

    status_code = 422
    code = "workflow_error"
    message = "The workflow could not be executed."


class RenderError(AppError):
    """A media render job failed."""

    status_code = 500
    code = "render_error"
    message = "A render job failed."


class QueueError(AppError):
    """A task/queue operation failed."""

    status_code = 500
    code = "queue_error"
    message = "A queue operation failed."

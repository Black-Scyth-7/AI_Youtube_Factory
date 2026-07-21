"""Application exception package."""

from app.exceptions.base import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.exceptions.handlers import register_exception_handlers

__all__ = [
    "AppError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceUnavailableError",
    "UnauthorizedError",
    "ValidationError",
    "register_exception_handlers",
]

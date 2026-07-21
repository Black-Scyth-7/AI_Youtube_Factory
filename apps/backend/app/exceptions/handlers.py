"""Global exception handlers.

Registers handlers that translate application errors, request-validation errors,
and uncaught exceptions into the shared :class:`ErrorResponse` envelope. Every
error body includes the current request id for log correlation.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base import AppError
from app.logging import get_logger, request_id_var
from app.schemas.common import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def _render(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details or {},
            request_id=request_id_var.get(),
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to ``app``."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error", extra={"code": exc.code, "status_code": exc.status_code}
        )
        return _render(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("request_validation_error", extra={"errors": exc.errors()})
        return _render(
            422,
            "validation_error",
            "The request failed validation.",
            {"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _render(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"error_type": type(exc).__name__})
        return _render(500, "internal_error", "An unexpected error occurred.")

"""Request context middleware.

Assigns each inbound request a request id and trace id, binds them to the
logging context, measures wall-clock duration, and echoes the identifiers back
on response headers. Downstream services can propagate an existing trace by
sending ``X-Request-ID`` / ``X-Trace-ID``.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import bind_request_context, clear_request_context, get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind per-request identifiers and emit an access log with duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        trace_id = request.headers.get(TRACE_ID_HEADER) or uuid.uuid4().hex
        bind_request_context(request_id=request_id, trace_id=trace_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request.failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            clear_request_context()

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        logger.info(
            "request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

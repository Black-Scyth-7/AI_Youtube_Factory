"""Request context middleware.

Assigns each inbound request a request id and opens a server span for it, binds
both to the logging context, measures wall-clock duration, and echoes the
identifiers back on response headers.

Trace continuation follows W3C Trace Context: a ``traceparent`` header joins
this request to the caller's trace, so a request crossing services shares one
trace id. ``X-Request-ID`` and ``X-Trace-ID`` remain accepted for callers that
do not speak Trace Context.
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import bind_request_context, clear_request_context, get_logger
from app.observability.tracing import TRACEPARENT_HEADER, SpanContext, start_span

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"

#: Inbound identifiers are echoed back on the response and written into every
#: log record, so they are constrained rather than trusted. Anything else is
#: replaced with a generated id.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _clean_id(value: str | None) -> str | None:
    """Return ``value`` if it is a safe identifier, else ``None``."""
    if value is None:
        return None
    value = value.strip()
    return value if _SAFE_ID_RE.match(value) else None


def _incoming_parent(request: Request) -> SpanContext | None:
    """The caller's span context, from ``traceparent`` or ``X-Trace-ID``."""
    traceparent = request.headers.get(TRACEPARENT_HEADER)
    if traceparent:
        parent = SpanContext.parse(traceparent)
        if parent is not None:
            return parent

    # X-Trace-ID carries no span id, so it can only seed the trace id. A value
    # that is not a valid trace id starts a fresh trace rather than producing
    # an id no trace viewer can resolve.
    legacy = _clean_id(request.headers.get(TRACE_ID_HEADER))
    if legacy and _TRACE_ID_RE.match(legacy.lower()):
        return SpanContext(trace_id=legacy.lower(), span_id="0" * 15 + "1")
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind per-request identifiers and emit an access log with duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = _clean_id(request.headers.get(REQUEST_ID_HEADER)) or uuid.uuid4().hex
        parent = _incoming_parent(request)

        try:
            with start_span(
                f"{request.method} {request.url.path}",
                kind="server",
                parent=parent,
                attributes={
                    "http.request.method": request.method,
                    "url.path": request.url.path,
                },
            ) as span:
                # Bound from the span rather than generated alongside it: the
                # two used to be separate ids, so the X-Trace-ID header named a
                # trace that the traceparent header disagreed with.
                trace_id = span.trace_id
                bind_request_context(request_id=request_id, trace_id=trace_id)
                try:
                    response = await call_next(request)
                except Exception:
                    # Logged inside the span and the bound context, so the
                    # record carries the request id and trace id.
                    logger.exception(
                        "request.failed",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "duration_ms": span.duration_ms,
                        },
                    )
                    raise

                span.set_attribute("http.response.status_code", response.status_code)
                response.headers[REQUEST_ID_HEADER] = request_id
                response.headers[TRACE_ID_HEADER] = trace_id
                response.headers[TRACEPARENT_HEADER] = span.context.to_traceparent()
                # Also emitted inside the span. This log used to sit after a
                # `finally` that had already cleared the context, so every
                # successful request's access log carried a null request id —
                # the one field that makes an access log searchable.
                logger.info(
                    "request.completed",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": span.duration_ms,
                    },
                )
                return response
        finally:
            clear_request_context()

"""Request-scoped logging context.

Uses :mod:`contextvars` so that identifiers (request id, trace id) set by
middleware are transparently available to every log record emitted while
handling that request, without threading them through call signatures.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def bind_request_context(*, request_id: str, trace_id: str) -> None:
    """Bind identifiers for the current request scope."""
    request_id_var.set(request_id)
    trace_id_var.set(trace_id)


def clear_request_context() -> None:
    """Reset identifiers at the end of a request scope."""
    request_id_var.set(None)
    trace_id_var.set(None)

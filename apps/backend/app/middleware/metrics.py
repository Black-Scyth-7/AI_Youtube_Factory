"""HTTP metrics middleware.

Records request counts, latency, in-flight depth, and unhandled exceptions.

The critical detail is the ``route`` label. Labelling by ``request.url.path``
gives one time series per distinct URL, so ``/api/v1/videos/{id}`` becomes a
series per video — unbounded, client-controlled, and the standard way a metrics
endpoint takes down the process it was meant to be monitoring. This labels by
the matched *route template* instead, and buckets anything that matched no
route under a single ``__unmatched__`` series.

The template is read from ``scope["route"]`` after the downstream call, since
that is what the router itself matched. Re-implementing the matching here to
get the label earlier was tried and is not worth it: FastAPI's route table
holds lazily-expanded router objects whose children are not walkable, so any
reimplementation silently degrades to ``__unmatched__`` on a version bump.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability import instruments

#: Label value for requests that matched no route (404s, probes for /wp-admin).
UNMATCHED_ROUTE = "__unmatched__"


def matched_route(request: Request) -> str:
    """The matched route's full path template, or ``UNMATCHED_ROUTE``.

    Only meaningful once routing has run.

    ``scope["route"]`` is the route as declared on its own router, so its
    ``path_format`` omits the ``include_router`` prefix — every router's
    ``/health`` would report as ``/health`` and share one series. FastAPI also
    records the *effective* route, whose path carries the prefix, so that is
    preferred and the bare template is the fallback.
    """
    # Read by key rather than importing FastAPI's private constants, and treat
    # every step as optional: a version that drops this leaves the labels less
    # specific, not the middleware broken.
    effective = request.scope.get("fastapi", {})
    if isinstance(effective, dict):
        context = effective.get("effective_route_context")
        path = getattr(context, "path", None)
        if isinstance(path, str) and path:
            return path

    path_format = getattr(request.scope.get("route"), "path_format", None)
    return path_format if isinstance(path_format, str) else UNMATCHED_ROUTE


def status_class(status_code: int) -> str:
    """Group a status code as ``2xx``/``4xx``/…, keeping the label bounded."""
    return f"{status_code // 100}xx"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Instrument every request with count, duration, and in-flight depth."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        method = request.method

        # In-flight is labelled by method alone. The route is not yet known
        # here, and a gauge whose increment and decrement disagree on a label
        # never returns to zero — a saturation alert that fires forever.
        instruments.http_requests_in_progress.inc(1.0, method=method)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            route = matched_route(request)
            instruments.http_request_exceptions_total.inc(
                1.0, route=route, exception=type(exc).__name__
            )
            # An exception escaping the handler still becomes a 500 for the
            # client, so it must appear in the request rate too — otherwise the
            # error budget silently ignores the worst failures.
            instruments.http_requests_total.inc(
                1.0, method=method, route=route, status="5xx"
            )
            instruments.http_request_duration_seconds.observe(
                time.perf_counter() - start, method=method, route=route
            )
            raise
        else:
            route = matched_route(request)
            instruments.http_requests_total.inc(
                1.0,
                method=method,
                route=route,
                status=status_class(response.status_code),
            )
            instruments.http_request_duration_seconds.observe(
                time.perf_counter() - start, method=method, route=route
            )
            return response
        finally:
            instruments.http_requests_in_progress.dec(1.0, method=method)

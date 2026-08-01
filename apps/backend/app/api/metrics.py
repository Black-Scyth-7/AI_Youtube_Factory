"""The Prometheus scrape endpoint.

Mounted at the application root rather than under the versioned API prefix:
``/metrics`` is where every scraper looks by default, and the exposition format
is versioned by its own content type, not by this application's API version.

The payload describes internal traffic shape, error rates, and spend. That is
useful to an operator and equally useful to an attacker mapping the service, so
setting ``METRICS_TOKEN`` requires a bearer token. Left empty, the endpoint is
open and must be restricted at the network layer instead.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Request, Response, status

from app.config import settings
from app.observability import metrics

router = APIRouter(tags=["observability"])


def _authorized(request: Request) -> bool:
    """Whether this scrape may proceed."""
    expected = settings.metrics_token
    if not expected:
        return True
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    # Constant-time: a token comparison that returns early leaks the token one
    # character at a time to anyone who can measure the response.
    return hmac.compare_digest(token.strip(), expected)


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    response_class=Response,
    include_in_schema=False,
    responses={
        200: {"content": {metrics.CONTENT_TYPE: {}}, "description": "Metrics exposition"},
        401: {"description": "Missing or invalid scrape token"},
        404: {"description": "Metrics are disabled"},
    },
)
async def prometheus_metrics(request: Request) -> Response:
    """Render the metric registry in the Prometheus text exposition format."""
    if not settings.metrics_enabled:
        # 404 rather than 403: a disabled endpoint should be indistinguishable
        # from one that was never mounted.
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    if not _authorized(request):
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)

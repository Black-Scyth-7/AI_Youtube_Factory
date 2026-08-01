"""FastAPI application factory and ASGI entrypoint.

Assembles the application: configures logging, builds the DI container, installs
middleware and exception handlers, mounts the versioned API, and manages startup
/ shutdown via an async lifespan. Swagger UI is served at ``/docs`` and ReDoc at
``/redoc``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.__version__ import __version__
from app.api.metrics import router as metrics_router
from app.api.v1 import api_v1_router
from app.config import settings
from app.core.di import build_container
from app.exceptions import register_exception_handlers
from app.logging import configure_logging, get_logger
from app.middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.observability import configure_tracing, shutdown_tracing
from app.observability.instruments import app_info

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    configure_tracing()
    # A constant-1 gauge, the standard way to expose build metadata: joining on
    # it labels any dashboard panel with the version that produced the data.
    app_info.set(1.0, version=__version__, environment=settings.environment.value)
    logger.info(
        "app.startup",
        extra={"version": __version__, "environment": settings.environment.value},
    )
    container = build_container()
    app.state.container = container
    try:
        yield
    finally:
        engine = container.engine()
        await engine.dispose()
        shutdown_tracing()
        logger.info("app.shutdown")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "AI YouTube Factory — autonomous research, generation, editing, "
            "optimization, publishing, and analysis of YouTube content."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Starlette runs these outermost-last: RequestContextMiddleware is added
    # last so it wraps everything and every inner log record is correlated.
    # MetricsMiddleware sits just inside it, timing the whole handler chain.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    # Unversioned and at the root: scrapers default to /metrics.
    app.include_router(metrics_router)

    return app


app = create_app()

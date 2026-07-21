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

from app.__version__ import __version__
from app.api.v1 import api_v1_router
from app.config import settings
from app.core.di import build_container
from app.exceptions import register_exception_handlers
from app.logging import configure_logging, get_logger
from app.middleware import RequestContextMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
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

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()

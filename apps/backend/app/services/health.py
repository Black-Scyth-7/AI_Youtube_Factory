"""Health/readiness probing service.

Performs best-effort connectivity checks against required infrastructure
dependencies (PostgreSQL, Redis, RabbitMQ). Each probe is isolated and
time-bounded so a single down dependency never blocks the readiness endpoint.
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.logging import get_logger
from app.schemas.common import HealthComponent, HealthStatus

logger = get_logger(__name__)

_PROBE_TIMEOUT_SECONDS = 3.0


async def _check_database() -> HealthComponent:
    """Probe PostgreSQL by opening a connection and running ``SELECT 1``."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(str(settings.database_url))
        try:
            async with asyncio.timeout(_PROBE_TIMEOUT_SECONDS):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()
        return HealthComponent(name="database", status="ok")
    except Exception as exc:
        logger.warning("healthcheck.database.down", extra={"error": str(exc)})
        return HealthComponent(name="database", status="down", detail=str(exc))


async def _check_redis() -> HealthComponent:
    """Probe Redis with a ``PING``."""
    try:
        import redis.asyncio as redis

        client = redis.from_url(str(settings.redis_url))
        try:
            async with asyncio.timeout(_PROBE_TIMEOUT_SECONDS):
                await client.ping()
        finally:
            await client.aclose()
        return HealthComponent(name="redis", status="ok")
    except Exception as exc:
        logger.warning("healthcheck.redis.down", extra={"error": str(exc)})
        return HealthComponent(name="redis", status="down", detail=str(exc))


async def _check_rabbitmq() -> HealthComponent:
    """Probe RabbitMQ by opening and closing a connection."""
    try:
        import aio_pika

        async with asyncio.timeout(_PROBE_TIMEOUT_SECONDS):
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            await connection.close()
        return HealthComponent(name="rabbitmq", status="ok")
    except Exception as exc:
        logger.warning("healthcheck.rabbitmq.down", extra={"error": str(exc)})
        return HealthComponent(name="rabbitmq", status="down", detail=str(exc))


async def collect_readiness() -> HealthStatus:
    """Run all dependency probes concurrently and aggregate the result."""
    components = await asyncio.gather(
        _check_database(), _check_redis(), _check_rabbitmq()
    )
    overall = "ok" if all(c.status == "ok" for c in components) else "degraded"
    return HealthStatus(status=overall, components=list(components))

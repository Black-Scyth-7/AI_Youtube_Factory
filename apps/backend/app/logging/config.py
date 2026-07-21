"""Structured logging configuration.

Emits one JSON object per log line with a stable field set (timestamp, level,
service, environment, request id, trace id, duration) so logs are queryable in
aggregation backends. A plain-text formatter is available for local development.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.__version__ import __version__
from app.config import settings
from app.logging.context import request_id_var, trace_id_var

_RESERVED_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
}


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON documents."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.app_name,
            "environment": settings.environment.value,
            "version": __version__,
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Attach any structured `extra=` fields passed by the caller.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)


class PlainLogFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )


def configure_logging() -> None:
    """Install the root logging configuration for the application."""
    formatter: logging.Formatter = (
        JsonLogFormatter() if settings.log_json else PlainLogFormatter()
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Align uvicorn's loggers with our formatter and level.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)

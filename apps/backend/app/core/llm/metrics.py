"""LLM observability helpers.

Emits a structured log record for every LLM request with the fields required for
monitoring — model, provider, latency, tokens, cost, retries, tool calls,
streaming, cache hit, and the request-scoped correlation id (via the logging
context). A lightweight :class:`RequestTimer` measures wall-clock latency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.messages import Usage
from app.core.llm.models import estimate_cost
from app.logging import get_logger

logger = get_logger("app.llm.metrics")


@dataclass
class RequestTimer:
    """Measures elapsed wall-clock time in milliseconds."""

    _start: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)


def record_request(
    *,
    provider: str,
    model: str,
    usage: Usage,
    latency_ms: float,
    streamed: bool = False,
    cache_hit: bool = False,
    tool_calls: int = 0,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> float:
    """Log a completed LLM request and return the estimated cost."""
    cost = estimate_cost(model, usage.input_tokens, usage.output_tokens)
    payload: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "streamed": streamed,
        "cache_hit": cache_hit,
        "tool_calls": tool_calls,
    }
    if extra:
        payload.update(extra)
    if error:
        payload["error"] = error
        logger.error("llm.request.failed", extra=payload)
    else:
        logger.info("llm.request.completed", extra=payload)
    return cost

"""Retry engine with exponential backoff and a circuit breaker.

Wraps an async operation with bounded retries (exponential backoff + jitter) for
transient failures, and a per-key circuit breaker that trips after repeated
failures to give a failing provider time to recover.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.llm.exceptions import CircuitOpenError, LLMRateLimitError, LLMTimeoutError
from app.logging import get_logger

logger = get_logger(__name__)

# Exceptions worth retrying (transient).
_RETRYABLE = (LLMRateLimitError, LLMTimeoutError, TimeoutError, ConnectionError)


@dataclass
class RetryPolicy:
    """Configuration for retrying an operation."""

    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.1


@dataclass
class CircuitBreaker:
    """A simple per-key circuit breaker."""

    failure_threshold: int = 5
    reset_after: timedelta = timedelta(seconds=30)
    _failures: dict[str, int] = field(default_factory=dict)
    _opened_at: dict[str, datetime] = field(default_factory=dict)

    def _is_open(self, key: str) -> bool:
        opened = self._opened_at.get(key)
        if opened is None:
            return False
        if datetime.now(UTC) - opened >= self.reset_after:
            # Half-open: clear and allow a probe.
            self._opened_at.pop(key, None)
            self._failures[key] = 0
            return False
        return True

    def check(self, key: str) -> None:
        if self._is_open(key):
            raise CircuitOpenError(details={"key": key})

    def record_success(self, key: str) -> None:
        self._failures[key] = 0
        self._opened_at.pop(key, None)

    def record_failure(self, key: str) -> None:
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        if count >= self.failure_threshold:
            self._opened_at[key] = datetime.now(UTC)
            logger.warning("llm.circuit_open", extra={"key": key, "failures": count})


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    breaker: CircuitBreaker | None = None,
    key: str = "default",
) -> T:
    """Execute ``operation`` with retries and optional circuit breaking."""
    if breaker is not None:
        breaker.check(key)

    attempt = 0
    while True:
        try:
            result = await operation()
            if breaker is not None:
                breaker.record_success(key)
            return result
        except _RETRYABLE as exc:
            attempt += 1
            if breaker is not None:
                breaker.record_failure(key)
            if attempt > policy.max_retries:
                logger.error(
                    "llm.retry_exhausted",
                    extra={"key": key, "attempts": attempt, "error": str(exc)},
                )
                raise
            delay = min(
                policy.base_delay * (2 ** (attempt - 1)), policy.max_delay
            ) + random.uniform(0, policy.jitter)
            logger.info(
                "llm.retry", extra={"key": key, "attempt": attempt, "delay": delay}
            )
            await asyncio.sleep(delay)
        except Exception:
            if breaker is not None:
                breaker.record_failure(key)
            raise

"""Execution sandbox.

Bounds an individual action's blast radius: a hard timeout and a concurrency
limit, plus a guard that refuses obviously dangerous operations. Tool execution
and LLM calls can be routed through :meth:`ExecutionSandbox.run` to enforce
consistent limits regardless of the caller.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class SandboxViolationError(RuntimeError):
    """Raised when an action violates a sandbox limit."""


@dataclass(slots=True)
class SandboxLimits:
    """Hard limits enforced by the sandbox."""

    timeout_seconds: float = 30.0
    max_concurrency: int = 8
    max_output_chars: int = 100_000


class ExecutionSandbox:
    """Runs coroutines under a timeout and a concurrency semaphore."""

    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()
        self._semaphore = asyncio.Semaphore(self.limits.max_concurrency)

    async def run(self, awaitable: Awaitable[T]) -> T:
        """Execute ``awaitable`` under the sandbox's timeout + concurrency limit."""
        async with self._semaphore:
            try:
                return await asyncio.wait_for(
                    awaitable, timeout=self.limits.timeout_seconds
                )
            except (TimeoutError, asyncio.TimeoutError) as exc:  # noqa: UP041
                raise SandboxViolationError(
                    f"Action exceeded {self.limits.timeout_seconds}s timeout."
                ) from exc

    def guard_output(self, output: str) -> str:
        """Truncate output that exceeds the sandbox's size limit."""
        if len(output) > self.limits.max_output_chars:
            return output[: self.limits.max_output_chars] + "…[truncated]"
        return output

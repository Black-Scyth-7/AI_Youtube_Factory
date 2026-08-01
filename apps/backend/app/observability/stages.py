"""Instrumentation for pipeline stages.

A decorator rather than inline timing: each stage method has its own signature,
and the recording is identical for all of them. Applied at the definition, so a
stage cannot be added without a visible decision about whether it is measured.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from app.observability import instruments
from app.observability.tracing import start_span

_P = ParamSpec("_P")
_R = TypeVar("_R")


def track_stage(
    stage: str,
) -> Callable[[Callable[_P, Awaitable[_R]]], Callable[_P, Awaitable[_R]]]:
    """Time an async pipeline stage, counting its outcome and opening a span."""

    def decorate(func: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            started = time.perf_counter()
            outcome = "failed"
            try:
                with start_span(
                    f"pipeline.{stage}", attributes={"pipeline.stage": stage}
                ):
                    result = await func(*args, **kwargs)
                outcome = "succeeded"
                return result
            finally:
                instruments.pipeline_stages_total.inc(1.0, stage=stage, outcome=outcome)
                instruments.pipeline_stage_duration_seconds.observe(
                    time.perf_counter() - started, stage=stage
                )

        return wrapper

    return decorate


def record_artifact_size(stage: str, size_bytes: int | None) -> None:
    """Record the size of an artifact a stage produced, when it reported one."""
    if size_bytes is None:
        return
    instruments.pipeline_artifact_bytes.observe(float(size_bytes), stage=stage)

"""Shared enumerations."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle states for an asynchronous job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"

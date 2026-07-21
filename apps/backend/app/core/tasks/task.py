"""Task model shared by the queue abstraction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """Lifecycle of a queued task."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskPriority(IntEnum):
    """Relative scheduling priority (higher runs first)."""

    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass(slots=True)
class TaskSpec:
    """A request to run a named task with arguments and policy."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    delay_seconds: float = 0.0
    max_retries: int = 3
    timeout_seconds: float | None = None


@dataclass(slots=True)
class TaskRecord:
    """Tracks the state and progress of a submitted task."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Any = None
    error: str | None = None
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)

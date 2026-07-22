"""Runtime task model and dependency graph.

An :class:`AgentTask` is a single unit of work produced by the planner and run
by the executor. Tasks form a dependency graph; :class:`TaskGraph` resolves a
safe execution order and the set of tasks that may run in parallel.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """Lifecycle of an agent task."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskKind(StrEnum):
    """What kind of work a task performs."""

    REASON = "reason"
    LLM = "llm"
    TOOL = "tool"
    WORKFLOW = "workflow"
    DELEGATE = "delegate"
    CUSTOM = "custom"


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass(slots=True)
class AgentTask:
    """A single planned unit of work."""

    description: str
    kind: TaskKind = TaskKind.REASON
    key: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    depends_on: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    max_retries: int = 2
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    progress: float = 0.0
    result: Any = None
    error: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.key:
            self.key = self.id.hex[:8]

    def log(self, message: str) -> None:
        """Append a timestamped log line to the task."""
        self.logs.append(f"{datetime.now(UTC).isoformat()} {message}")


class TaskGraph:
    """A dependency graph of tasks with topological scheduling."""

    def __init__(self, tasks: list[AgentTask] | None = None) -> None:
        self._tasks: dict[str, AgentTask] = {}
        for task in tasks or []:
            self.add(task)

    def add(self, task: AgentTask) -> None:
        """Add a task to the graph (keyed by ``task.key``)."""
        self._tasks[task.key] = task

    @property
    def tasks(self) -> list[AgentTask]:
        return list(self._tasks.values())

    def get(self, key: str) -> AgentTask | None:
        return self._tasks.get(key)

    def ready(self) -> list[AgentTask]:
        """Return pending tasks whose dependencies have all succeeded."""
        out: list[AgentTask] = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps = [self._tasks.get(d) for d in task.depends_on]
            if all(d is not None and d.status == TaskStatus.SUCCEEDED for d in deps):
                out.append(task)
        return sorted(out, key=lambda t: t.priority, reverse=True)

    def topological_order(self) -> list[AgentTask]:
        """Return tasks in a valid execution order (raises on a cycle)."""
        indegree: dict[str, int] = dict.fromkeys(self._tasks, 0)
        for task in self._tasks.values():
            for dep in task.depends_on:
                if dep in self._tasks:
                    indegree[task.key] += 1
        queue: deque[str] = deque(k for k, d in indegree.items() if d == 0)
        order: list[AgentTask] = []
        while queue:
            key = queue.popleft()
            order.append(self._tasks[key])
            for task in self._tasks.values():
                if key in task.depends_on:
                    indegree[task.key] -= 1
                    if indegree[task.key] == 0:
                        queue.append(task.key)
        if len(order) != len(self._tasks):
            raise ValueError("Task dependency graph contains a cycle.")
        return order

    def is_complete(self) -> bool:
        """Return ``True`` when no task is still pending or running."""
        return all(
            t.status not in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING)
            for t in self._tasks.values()
        )

    def has_failure(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self._tasks.values())

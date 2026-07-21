"""Task queue abstraction.

Defines the :class:`TaskQueue` protocol and an :class:`InMemoryTaskQueue` used in
development and tests. Handlers are registered by name; submissions return a
:class:`TaskRecord` whose status/progress can be polled. The same submission API
maps onto Celery/RabbitMQ/Temporal backends in later phases.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from app.core.tasks.task import TaskRecord, TaskSpec, TaskStatus
from app.exceptions.base import NotFoundError, QueueError
from app.logging import get_logger

logger = get_logger(__name__)

TaskHandler = Callable[[dict[str, Any], TaskRecord], Awaitable[Any]]


@runtime_checkable
class TaskQueue(Protocol):
    """Submit and track background tasks."""

    def register(self, name: str, handler: TaskHandler) -> None: ...

    async def submit(self, spec: TaskSpec) -> TaskRecord: ...

    def get(self, task_id: uuid.UUID) -> TaskRecord | None: ...

    async def cancel(self, task_id: uuid.UUID) -> None: ...


class InMemoryTaskQueue(TaskQueue):
    """Runs tasks as asyncio tasks in-process with retry, timeout, and cancel."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}
        self._records: dict[uuid.UUID, TaskRecord] = {}
        self._running: dict[uuid.UUID, asyncio.Task[None]] = {}

    def register(self, name: str, handler: TaskHandler) -> None:
        self._handlers[name] = handler

    async def submit(self, spec: TaskSpec) -> TaskRecord:
        if spec.name not in self._handlers:
            raise QueueError(f"No handler registered for task '{spec.name}'.")
        record = TaskRecord(name=spec.name)
        record.status = TaskStatus.SCHEDULED if spec.delay_seconds else TaskStatus.PENDING
        self._records[record.id] = record
        self._running[record.id] = asyncio.create_task(self._run(spec, record))
        return record

    def get(self, task_id: uuid.UUID) -> TaskRecord | None:
        return self._records.get(task_id)

    async def cancel(self, task_id: uuid.UUID) -> None:
        task = self._running.get(task_id)
        record = self._records.get(task_id)
        if task is None or record is None:
            raise NotFoundError("Task not found.")
        task.cancel()
        record.status = TaskStatus.CANCELLED
        record.touch()

    async def wait(self, task_id: uuid.UUID) -> TaskRecord:
        """Await completion of a task (test/utility helper)."""
        task = self._running.get(task_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        record = self._records.get(task_id)
        if record is None:
            raise NotFoundError("Task not found.")
        return record

    async def _run(self, spec: TaskSpec, record: TaskRecord) -> None:
        handler = self._handlers[spec.name]
        if spec.delay_seconds:
            await asyncio.sleep(spec.delay_seconds)
        while True:
            record.attempts += 1
            record.status = TaskStatus.RUNNING
            record.touch()
            try:
                coro = handler(spec.payload, record)
                if spec.timeout_seconds:
                    record.result = await asyncio.wait_for(coro, spec.timeout_seconds)
                else:
                    record.result = await coro
                record.status = TaskStatus.SUCCEEDED
                record.progress = 1.0
                record.touch()
                return
            except asyncio.CancelledError:
                record.status = TaskStatus.CANCELLED
                record.touch()
                return
            except TimeoutError:
                record.status = TaskStatus.TIMED_OUT
                record.error = "Task timed out."
                record.touch()
                return
            except Exception as exc:
                record.error = str(exc)
                if record.attempts > spec.max_retries:
                    record.status = TaskStatus.FAILED
                    record.touch()
                    logger.error(
                        "task.failed", extra={"task": spec.name, "error": str(exc)}
                    )
                    return
                record.status = TaskStatus.RETRYING
                record.touch()


_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    """Return the process task-queue singleton."""
    global _queue
    if _queue is None:
        _queue = InMemoryTaskQueue()
    return _queue


def set_task_queue(queue: TaskQueue) -> None:
    """Override the task-queue singleton (used in tests)."""
    global _queue
    _queue = queue

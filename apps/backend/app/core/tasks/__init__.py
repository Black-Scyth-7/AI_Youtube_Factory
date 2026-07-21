"""Task and queue abstraction (in-memory now; Celery/Temporal later)."""

from app.core.tasks.queue import (
    InMemoryTaskQueue,
    TaskHandler,
    TaskQueue,
    get_task_queue,
    set_task_queue,
)
from app.core.tasks.task import (
    TaskPriority,
    TaskRecord,
    TaskSpec,
    TaskStatus,
)

__all__ = [
    "InMemoryTaskQueue",
    "TaskHandler",
    "TaskPriority",
    "TaskQueue",
    "TaskRecord",
    "TaskSpec",
    "TaskStatus",
    "get_task_queue",
    "set_task_queue",
]

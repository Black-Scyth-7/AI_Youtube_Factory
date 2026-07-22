"""Agent domain events.

Published on the shared Phase 03 :class:`EventBus` so other parts of the system
(monitoring, persistence, future subscribers) can react to an agent's lifecycle
without coupling to the runtime. All events subclass the framework ``Event``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.events.bus import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentStarted(Event):
    run_id: uuid.UUID
    agent_slug: str
    goal: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskCreated(Event):
    run_id: uuid.UUID
    task_key: str
    description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskFinished(Event):
    run_id: uuid.UUID
    task_key: str
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolExecuted(Event):
    run_id: uuid.UUID
    tool_name: str
    success: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ReflectionFinished(Event):
    run_id: uuid.UUID
    lessons: int


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalCompleted(Event):
    run_id: uuid.UUID
    agent_slug: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GoalFailed(Event):
    run_id: uuid.UUID
    agent_slug: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentStopped(Event):
    run_id: uuid.UUID
    agent_slug: str
    state: str

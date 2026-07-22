"""Agent lifecycle states and legal transitions.

A small explicit state machine keeps the manager, monitor, and API in agreement
about what an agent is doing and what transitions are valid.
"""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    """The lifecycle state of a running agent."""

    CREATED = "created"
    INITIALIZING = "initializing"
    IDLE = "idle"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# States from which no further work happens.
TERMINAL_STATES: frozenset[AgentState] = frozenset(
    {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}
)

# Active "working" states (used by the monitor to count busy agents).
ACTIVE_STATES: frozenset[AgentState] = frozenset(
    {
        AgentState.PLANNING,
        AgentState.REASONING,
        AgentState.EXECUTING,
        AgentState.REFLECTING,
    }
)

_TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.CREATED: frozenset({AgentState.INITIALIZING, AgentState.CANCELLED}),
    AgentState.INITIALIZING: frozenset({AgentState.IDLE, AgentState.FAILED}),
    AgentState.IDLE: frozenset(
        {AgentState.PLANNING, AgentState.PAUSED, AgentState.CANCELLED}
    ),
    AgentState.PLANNING: frozenset(
        {
            AgentState.REASONING,
            AgentState.EXECUTING,
            AgentState.FAILED,
            AgentState.PAUSED,
            AgentState.CANCELLED,
        }
    ),
    AgentState.REASONING: frozenset(
        {
            AgentState.EXECUTING,
            AgentState.REFLECTING,
            AgentState.FAILED,
            AgentState.PAUSED,
            AgentState.CANCELLED,
        }
    ),
    AgentState.EXECUTING: frozenset(
        {
            AgentState.REFLECTING,
            AgentState.REASONING,
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.PAUSED,
            AgentState.CANCELLED,
        }
    ),
    AgentState.REFLECTING: frozenset(
        {
            AgentState.IDLE,
            AgentState.PLANNING,
            AgentState.COMPLETED,
            AgentState.FAILED,
            AgentState.PAUSED,
            AgentState.CANCELLED,
        }
    ),
    AgentState.PAUSED: frozenset({AgentState.IDLE, AgentState.CANCELLED}),
    AgentState.COMPLETED: frozenset(),
    AgentState.FAILED: frozenset(),
    AgentState.CANCELLED: frozenset(),
}


def can_transition(current: AgentState, target: AgentState) -> bool:
    """Return whether moving from ``current`` to ``target`` is allowed."""
    return target in _TRANSITIONS.get(current, frozenset())


class InvalidTransitionError(RuntimeError):
    """Raised when an illegal lifecycle transition is attempted."""

    def __init__(self, current: AgentState, target: AgentState) -> None:
        super().__init__(f"Cannot transition from {current} to {target}.")
        self.current = current
        self.target = target

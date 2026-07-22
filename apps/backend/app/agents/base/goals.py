"""Goal system.

A goal is the unit of intent handed to an agent. It carries the objective, its
priority and deadline, constraints, the expected output, machine-checkable
success criteria, and dependencies on other goals.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum


class GoalStatus(StrEnum):
    """Lifecycle of a goal."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalPriority(IntEnum):
    """Relative goal priority (higher is more urgent)."""

    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass(slots=True)
class SuccessCriterion:
    """A single, checkable condition for goal success."""

    description: str
    satisfied: bool = False


@dataclass(slots=True)
class Goal:
    """A goal handed to an agent."""

    objective: str
    priority: GoalPriority = GoalPriority.NORMAL
    deadline: datetime | None = None
    constraints: list[str] = field(default_factory=list)
    expected_output: str | None = None
    success_criteria: list[SuccessCriterion] = field(default_factory=list)
    dependencies: list[uuid.UUID] = field(default_factory=list)
    status: GoalStatus = GoalStatus.PENDING
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def is_satisfied(self) -> bool:
        """Return ``True`` when all declared success criteria are satisfied.

        A goal with no explicit criteria is considered satisfied once its status
        is marked completed (the agent's own judgement).
        """
        if not self.success_criteria:
            return self.status == GoalStatus.COMPLETED
        return all(c.satisfied for c in self.success_criteria)

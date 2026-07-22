"""Multi-agent coordination.

Coordinates several agents working towards a shared goal. Roles follow the
classic pattern: a *supervisor* decomposes and synthesizes, *workers* execute
subgoals, a *coordinator* routes work, and *observers* watch without acting.
Workers share memory and a message bus; the supervisor merges their results.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.agents.base.goals import Goal, GoalStatus
from app.agents.communication.bus import AgentMessage, MessageBus, MessageType
from app.agents.manager.manager import AgentManager, get_agent_manager
from app.logging import get_logger

logger = get_logger(__name__)


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    WORKER = "worker"
    COORDINATOR = "coordinator"
    OBSERVER = "observer"


@dataclass(slots=True)
class SubGoalResult:
    """The result of a delegated subgoal."""

    subgoal: str
    worker: str
    output: str
    status: GoalStatus


@dataclass(slots=True)
class CoordinationResult:
    """The aggregate result of a multi-agent run."""

    run_id: uuid.UUID
    subgoals: list[SubGoalResult] = field(default_factory=list)
    final_output: str = ""
    shared_memory: dict[str, Any] = field(default_factory=dict)


class MultiAgentCoordinator:
    """Delegates subgoals to worker agents and synthesizes via a supervisor."""

    def __init__(
        self,
        *,
        manager: AgentManager | None = None,
        supervisor_slug: str = "assistant",
    ) -> None:
        self._manager = manager or get_agent_manager()
        self._supervisor = supervisor_slug
        self._workers: list[str] = []
        self._roles: dict[str, AgentRole] = {supervisor_slug: AgentRole.SUPERVISOR}
        self.bus = MessageBus()
        self.shared_memory: dict[str, Any] = {}
        self.bus.register(supervisor_slug)

    def add_worker(self, slug: str) -> None:
        """Register a worker agent."""
        self._workers.append(slug)
        self._roles[slug] = AgentRole.WORKER
        self.bus.register(slug)

    def add_observer(self, slug: str) -> None:
        self._roles[slug] = AgentRole.OBSERVER
        self.bus.register(slug)

    def role_of(self, slug: str) -> AgentRole:
        return self._roles.get(slug, AgentRole.WORKER)

    async def coordinate(
        self, objective: str, subgoals: list[str], **context_kwargs: Any
    ) -> CoordinationResult:
        """Run ``subgoals`` across workers, then synthesize with the supervisor."""
        run_id = uuid.uuid4()
        result = CoordinationResult(run_id=run_id)
        if not self._workers:
            self._workers = [self._supervisor]

        for index, subgoal in enumerate(subgoals):
            worker = self._workers[index % len(self._workers)]
            self.bus.send(
                AgentMessage(
                    sender=self._supervisor,
                    recipient=worker,
                    content=subgoal,
                    type=MessageType.DELEGATE,
                )
            )
            run = await self._manager.run(
                worker, Goal(objective=subgoal), **context_kwargs
            )
            self.shared_memory[f"subgoal_{index}"] = run.output
            self.bus.send(
                AgentMessage(
                    sender=worker,
                    recipient=self._supervisor,
                    content=run.output,
                    type=MessageType.RESPONSE,
                )
            )
            result.subgoals.append(
                SubGoalResult(
                    subgoal=subgoal,
                    worker=worker,
                    output=run.output,
                    status=run.goal_status,
                )
            )

        synthesis = await self._synthesize(objective, result, **context_kwargs)
        result.final_output = synthesis
        result.shared_memory = dict(self.shared_memory)
        logger.info(
            "agent.coordinate.done",
            extra={"run_id": str(run_id), "subgoals": len(subgoals)},
        )
        return result

    async def _synthesize(
        self, objective: str, result: CoordinationResult, **context_kwargs: Any
    ) -> str:
        findings = "\n".join(f"- {sr.subgoal}: {sr.output}" for sr in result.subgoals)
        goal = Goal(
            objective=f"Synthesize a final answer for: {objective}",
            constraints=[f"Incorporate these worker findings:\n{findings}"],
            expected_output="A single consolidated result.",
        )
        run = await self._manager.run(self._supervisor, goal, **context_kwargs)
        return run.output

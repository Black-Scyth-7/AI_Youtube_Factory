"""Agent manager.

Owns the lifecycle of running agent instances: create from the registry, run,
pause/resume/cancel/restart, track health and metrics, and expose the set of
active agents. This is the in-process runtime coordinator; the service layer
wraps it with persistence and RBAC.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.base.agent import AgentRunResult, BaseAgent
from app.agents.base.goals import Goal
from app.agents.base.lifecycle import AgentState
from app.agents.registry.registry import AgentRegistry, get_agent_registry
from app.logging import get_logger

if TYPE_CHECKING:
    from app.agents.base.config import AgentConfig

logger = get_logger(__name__)


@dataclass(slots=True)
class ManagedAgent:
    """A tracked, running agent instance."""

    run_id: uuid.UUID
    slug: str
    agent: BaseAgent
    goal: Goal
    task: asyncio.Task[AgentRunResult] | None = None
    result: AgentRunResult | None = None
    started_at: float = 0.0

    @property
    def state(self) -> AgentState:
        return self.agent.state


@dataclass(slots=True)
class ManagerHealth:
    """A snapshot of manager-wide health."""

    active: int = 0
    by_state: dict[str, int] = field(default_factory=dict)


class AgentManager:
    """Creates and supervises agent instances."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or get_agent_registry()
        self._active: dict[uuid.UUID, ManagedAgent] = {}

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    def create(self, slug: str, version: str | None = None) -> BaseAgent:
        """Instantiate a registered agent."""
        return self._registry.create(slug, version)

    async def run(
        self,
        slug: str,
        goal: Goal,
        *,
        version: str | None = None,
        config: AgentConfig | None = None,
        **context_kwargs: Any,
    ) -> AgentRunResult:
        """Run an agent to completion, tracking it while active."""
        agent = self.create(slug, version)
        managed = ManagedAgent(run_id=uuid.uuid4(), slug=slug, agent=agent, goal=goal)
        self._active[managed.run_id] = managed
        logger.info(
            "agent.manager.run", extra={"slug": slug, "run_id": str(managed.run_id)}
        )
        try:
            result = await agent.run(
                goal, config=config, run_id=managed.run_id, **context_kwargs
            )
            managed.result = result
            return result
        finally:
            self._active.pop(managed.run_id, None)

    def pause(self, run_id: uuid.UUID) -> bool:
        managed = self._active.get(run_id)
        if managed is None:
            return False
        managed.agent.pause()
        return True

    def resume(self, run_id: uuid.UUID) -> bool:
        managed = self._active.get(run_id)
        if managed is None:
            return False
        managed.agent.resume()
        return True

    def cancel(self, run_id: uuid.UUID) -> bool:
        managed = self._active.get(run_id)
        if managed is None:
            return False
        managed.agent.cancel()
        if managed.task is not None:
            managed.task.cancel()
        return True

    def get(self, run_id: uuid.UUID) -> ManagedAgent | None:
        return self._active.get(run_id)

    def running(self) -> list[ManagedAgent]:
        return list(self._active.values())

    def health(self) -> ManagerHealth:
        """Return a manager-wide health snapshot."""
        by_state: dict[str, int] = {}
        for managed in self._active.values():
            key = managed.state.value
            by_state[key] = by_state.get(key, 0) + 1
        return ManagerHealth(active=len(self._active), by_state=by_state)


_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    """Return the process agent-manager singleton."""
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager


def set_agent_manager(manager: AgentManager) -> None:
    """Override the agent-manager singleton (used in tests)."""
    global _manager
    _manager = manager

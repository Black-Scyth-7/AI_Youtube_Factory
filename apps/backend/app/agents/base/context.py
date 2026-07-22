"""Agent runtime context.

The :class:`AgentContext` bundles everything the engine components (planner,
reasoner, executor, reflector, evaluator) need to do their work: the agent's
identity, active goal, configuration, memory, knowledge, tools, policy enforcer,
the LLM bridge, an event publisher, and a running metrics accumulator. It is the
single object threaded through a run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.agents.base.config import AgentConfig
from app.agents.base.goals import Goal
from app.agents.base.identity import AgentIdentity
from app.agents.base.llm import AgentLLM, ManagerLLM
from app.agents.knowledge.knowledge import KnowledgeBase
from app.agents.memory.memory import AgentMemoryStore
from app.agents.policies.policies import AgentPolicy, PolicyEnforcer
from app.agents.tools.builtins import default_tools
from app.agents.tools.registry import AgentToolRegistry
from app.core.events import EventBus, get_event_bus
from app.logging import get_logger


@dataclass(slots=True)
class RunMetrics:
    """Cumulative metrics for a single agent run."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
    llm_calls: int = 0
    tasks_total: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    retries: int = 0
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add_llm(self, *, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd
        self.llm_calls += 1


class AgentContext:
    """Everything an agent needs while running a goal."""

    def __init__(
        self,
        *,
        identity: AgentIdentity,
        goal: Goal,
        config: AgentConfig | None = None,
        memory: AgentMemoryStore | None = None,
        knowledge: KnowledgeBase | None = None,
        tools: AgentToolRegistry | None = None,
        policy: AgentPolicy | None = None,
        llm: AgentLLM | None = None,
        events: EventBus | None = None,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> None:
        self.identity = identity
        self.goal = goal
        self.config = config or AgentConfig()
        self.memory = memory or AgentMemoryStore(
            max_context_tokens=self.config.max_tokens * 2
        )
        self.knowledge = knowledge or KnowledgeBase()
        self.tools = tools or _default_registry()
        self.enforcer = PolicyEnforcer(policy)
        self.llm: AgentLLM = llm or ManagerLLM(model=self.config.model)
        self.events = events or get_event_bus()
        self.organization_id = organization_id
        self.user_id = user_id
        self.run_id = run_id or uuid.uuid4()
        self.metrics = RunMetrics()
        self.blackboard: dict[str, Any] = {}
        self.logger = get_logger(f"agent.{identity.slug}")

    def rate_limit_key(self) -> str:
        return str(self.organization_id or "global")

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Run an LLM completion, recording usage against policy + metrics."""
        reply = await self.llm.complete(
            prompt,
            system=system or self.config.system_prompt,
            max_tokens=self.config.max_tokens,
        )
        self.metrics.add_llm(
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_usd=reply.cost_usd,
        )
        self.enforcer.add_usage(cost_usd=reply.cost_usd, tokens=reply.total_tokens)
        return reply.text


def _default_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register_all(default_tools())
    return registry

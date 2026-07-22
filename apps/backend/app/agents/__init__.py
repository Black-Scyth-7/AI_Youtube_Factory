"""Autonomous AI Agent framework.

A generic, provider-independent platform for planning, reasoning, tool use,
memory, reflection, evaluation, scheduling, and multi-agent collaboration. Every
future AI capability (research, scripting, SEO, analytics, video generation)
builds on this framework and reaches models only through the Phase 04 LLM layer.

Public surface:

* :class:`BaseAgent` — the abstract agent every agent inherits.
* :class:`AgentManager` / :class:`AgentRegistry` — lifecycle + discovery.
* :class:`Goal` / :class:`AgentContext` — the inputs and runtime state.
"""

from app.agents.base.agent import AgentRunResult, BaseAgent
from app.agents.base.config import AgentConfig
from app.agents.base.context import AgentContext
from app.agents.base.goals import Goal, GoalPriority, GoalStatus
from app.agents.base.identity import AgentIdentity
from app.agents.base.lifecycle import AgentState
from app.agents.manager.manager import (
    AgentManager,
    get_agent_manager,
    set_agent_manager,
)
from app.agents.registry.registry import (
    AgentRegistry,
    get_agent_registry,
    set_agent_registry,
)

__all__ = [
    "AgentConfig",
    "AgentContext",
    "AgentIdentity",
    "AgentManager",
    "AgentRegistry",
    "AgentRunResult",
    "AgentState",
    "BaseAgent",
    "Goal",
    "GoalPriority",
    "GoalStatus",
    "get_agent_manager",
    "get_agent_registry",
    "set_agent_manager",
    "set_agent_registry",
]

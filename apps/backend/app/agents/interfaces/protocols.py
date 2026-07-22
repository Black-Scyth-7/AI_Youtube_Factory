"""Structural interfaces for the agent framework.

These ``Protocol`` definitions let every moving part of an agent (planner,
reasoner, executor, reflector, evaluator, memory, knowledge, tools) be swapped
for an alternative implementation without changing the :class:`BaseAgent`. The
default concrete implementations live in their respective packages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext
    from app.agents.base.goals import Goal
    from app.agents.base.tasks import AgentTask, TaskGraph
    from app.agents.evaluation.evaluator import Evaluation
    from app.agents.reasoning.reasoner import ReasoningTrace
    from app.agents.reflection.reflector import Reflection
    from app.agents.tools.registry import AgentTool, ToolOutcome


@runtime_checkable
class Planner(Protocol):
    """Decomposes a goal into an executable task graph."""

    async def plan(self, goal: Goal, context: AgentContext) -> TaskGraph: ...

    async def replan(
        self, goal: Goal, graph: TaskGraph, context: AgentContext
    ) -> TaskGraph: ...


@runtime_checkable
class Reasoner(Protocol):
    """Produces structured reasoning for a task."""

    async def reason(self, task: AgentTask, context: AgentContext) -> ReasoningTrace: ...


@runtime_checkable
class Executor(Protocol):
    """Runs a single task to completion."""

    async def execute(self, task: AgentTask, context: AgentContext) -> Any: ...


@runtime_checkable
class Reflector(Protocol):
    """Analyzes results and produces lessons."""

    async def reflect(self, graph: TaskGraph, context: AgentContext) -> Reflection: ...


@runtime_checkable
class Evaluator(Protocol):
    """Scores the quality of an agent run."""

    async def evaluate(self, graph: TaskGraph, context: AgentContext) -> Evaluation: ...


@runtime_checkable
class MemoryStore(Protocol):
    """Working + episodic memory for an agent."""

    def remember(self, scope: str, key: str, value: Any) -> None: ...

    def recall(self, scope: str, key: str) -> Any: ...

    def scope_items(self, scope: str) -> dict[str, Any]: ...


@runtime_checkable
class KnowledgeStore(Protocol):
    """Read-only knowledge available to an agent."""

    def search(self, query: str, *, limit: int = 5) -> list[str]: ...


@runtime_checkable
class ToolProvider(Protocol):
    """Discovers and executes tools."""

    def list_tools(self) -> list[AgentTool]: ...

    def get(self, name: str) -> AgentTool | None: ...

    async def run(self, name: str, arguments: dict[str, Any]) -> ToolOutcome: ...

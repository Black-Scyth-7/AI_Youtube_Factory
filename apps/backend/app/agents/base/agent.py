"""Base agent.

:class:`BaseAgent` is the abstract core every concrete agent inherits. It wires
the engine components (planner, reasoner, executor, reflector, evaluator) around
a single :class:`AgentContext` and drives the full lifecycle:

    initialize -> plan -> reason -> execute -> reflect -> learn -> evaluate
    -> finish

plus ``cancel`` / ``pause`` / ``resume`` / ``health``. The reasoning pipeline is
integrated into execution (the executor reasons before acting). Subclasses
customize behavior by overriding :meth:`configure` (register tools/knowledge) and
:meth:`final_output`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.base.context import AgentContext, RunMetrics
from app.agents.base.goals import Goal, GoalStatus
from app.agents.base.identity import AgentIdentity
from app.agents.base.lifecycle import (
    AgentState,
    InvalidTransitionError,
    can_transition,
)
from app.agents.base.tasks import TaskGraph, TaskStatus
from app.agents.evaluation.evaluator import Evaluation, Evaluator
from app.agents.events.events import (
    AgentStarted,
    AgentStopped,
    GoalCompleted,
    GoalFailed,
)
from app.agents.executor.executor import Executor
from app.agents.planner.planner import Planner
from app.agents.reasoning.reasoner import Reasoner
from app.agents.reflection.reflector import Reflection, Reflector

if TYPE_CHECKING:
    from app.agents.base.config import AgentConfig


@dataclass(slots=True)
class AgentRunResult:
    """The full result of an agent run."""

    run_id: str
    state: AgentState
    output: str
    goal_status: GoalStatus
    metrics: RunMetrics
    graph: TaskGraph
    reflection: Reflection | None = None
    evaluation: Evaluation | None = None
    error: str | None = None
    reasoning_log: list[str] = field(default_factory=list)


class BaseAgent:
    """Abstract base class for all agents."""

    #: Concrete agents should override these class attributes.
    name: str = "Base Agent"
    slug: str = "base"
    description: str = ""
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    category: str = "general"

    def __init__(
        self,
        *,
        planner: Planner | None = None,
        reasoner: Reasoner | None = None,
        executor: Executor | None = None,
        reflector: Reflector | None = None,
        evaluator: Evaluator | None = None,
    ) -> None:
        self._reasoner = reasoner or Reasoner()
        self._planner = planner or Planner()
        self._executor = executor or Executor(self._reasoner)
        self._reflector = reflector or Reflector()
        self._evaluator = evaluator or Evaluator()
        self.state = AgentState.CREATED
        self._paused = False
        self._cancelled = False
        self.context: AgentContext | None = None

    # -- Identity ---------------------------------------------------------
    @classmethod
    def identity(cls) -> AgentIdentity:
        """Return the identity describing this agent class."""
        return AgentIdentity(
            name=cls.name,
            slug=cls.slug,
            description=cls.description,
            version=cls.version,
            capabilities=cls.capabilities,
            tags=cls.tags,
            category=cls.category,
        )

    # -- Lifecycle transitions -------------------------------------------
    def _transition(self, target: AgentState) -> None:
        if not can_transition(self.state, target):
            raise InvalidTransitionError(self.state, target)
        self.state = target

    def pause(self) -> None:
        """Request the run pause at the next safe point."""
        self._paused = True

    def resume(self) -> None:
        """Clear a pause request."""
        self._paused = False

    def cancel(self) -> None:
        """Request cancellation at the next safe point."""
        self._cancelled = True

    def health(self) -> dict[str, Any]:
        """Return a health snapshot of the agent."""
        return {
            "slug": self.slug,
            "state": self.state.value,
            "paused": self._paused,
            "cancelled": self._cancelled,
        }

    # -- Customization hooks ---------------------------------------------
    async def configure(self, context: AgentContext) -> None:
        """Register tools/knowledge before the run. Override in subclasses."""
        return None

    def final_output(self, graph: TaskGraph, context: AgentContext) -> str:
        """Compute the final textual output. Override for custom synthesis."""
        synth = graph.get("synthesize")
        if synth is not None and synth.result:
            return str(synth.result)
        succeeded = [
            t for t in graph.topological_order() if t.status == TaskStatus.SUCCEEDED
        ]
        if succeeded and succeeded[-1].result:
            return str(succeeded[-1].result)
        return "No output produced."

    # -- Lifecycle methods ------------------------------------------------
    async def initialize(self, context: AgentContext) -> None:
        """Prepare the agent for a run."""
        self._transition(AgentState.INITIALIZING)
        await self.configure(context)
        await context.events.publish(
            AgentStarted(
                run_id=context.run_id,
                agent_slug=self.slug,
                goal=context.goal.objective,
            )
        )
        self._transition(AgentState.IDLE)

    async def plan(self, context: AgentContext) -> TaskGraph:
        """Decompose the goal into a task graph."""
        self._transition(AgentState.PLANNING)
        return await self._planner.plan(context.goal, context)

    async def execute(self, graph: TaskGraph, context: AgentContext) -> None:
        """Run the task graph to completion with bounded replanning."""
        self._transition(AgentState.EXECUTING)
        iterations = 0
        max_iterations = context.config.max_iterations
        while not graph.is_complete() and iterations < max_iterations:
            if self._cancelled:
                return
            while self._paused and not self._cancelled:
                self.state = AgentState.PAUSED
                return  # cooperative pause; caller may resume + re-run
            ready = graph.ready()
            if not ready:
                break
            for task in ready:
                await self._executor.execute(task, context)
            if graph.has_failure() and context.config.reflection_enabled:
                await self._planner.replan(context.goal, graph, context)
            iterations += 1

    async def reflect(self, graph: TaskGraph, context: AgentContext) -> Reflection:
        """Analyze the run and produce lessons."""
        self._transition(AgentState.REFLECTING)
        return await self._reflector.reflect(graph, context)

    async def learn(self, reflection: Reflection, context: AgentContext) -> None:
        """Persist lessons for future runs (memory already updated by reflect)."""
        context.memory.remember("agent", "last_reflection", reflection.summary)

    async def evaluate(self, graph: TaskGraph, context: AgentContext) -> Evaluation:
        """Score the run."""
        return await self._evaluator.evaluate(graph, context)

    async def finish(self, graph: TaskGraph, context: AgentContext) -> GoalStatus:
        """Mark the goal complete or failed based on the graph outcome."""
        if graph.has_failure() and not any(
            t.status == TaskStatus.SUCCEEDED for t in graph.tasks
        ):
            context.goal.status = GoalStatus.FAILED
            self._transition(AgentState.FAILED)
        else:
            context.goal.status = GoalStatus.COMPLETED
            # EXECUTING/REFLECTING -> COMPLETED
            if can_transition(self.state, AgentState.COMPLETED):
                self.state = AgentState.COMPLETED
        return context.goal.status

    # -- Orchestration ----------------------------------------------------
    async def run(
        self, goal: Goal, *, config: AgentConfig | None = None, **context_kwargs: Any
    ) -> AgentRunResult:
        """Run the full lifecycle for ``goal`` and return the result."""
        context = AgentContext(
            identity=self.identity(),
            goal=goal,
            config=config,
            **context_kwargs,
        )
        self.context = context
        start = time.perf_counter()
        goal.status = GoalStatus.ACTIVE
        error: str | None = None
        reflection: Reflection | None = None
        evaluation: Evaluation | None = None
        graph = TaskGraph()

        try:
            await self.initialize(context)
            graph = await self.plan(context)
            await self.execute(graph, context)
            if self._cancelled:
                self.state = AgentState.CANCELLED
                context.goal.status = GoalStatus.CANCELLED
            else:
                if context.config.reflection_enabled:
                    reflection = await self.reflect(graph, context)
                    await self.learn(reflection, context)
                if context.config.evaluation_enabled:
                    evaluation = await self.evaluate(graph, context)
                await self.finish(graph, context)
        except Exception as exc:
            error = str(exc)
            self.state = AgentState.FAILED
            context.goal.status = GoalStatus.FAILED
            context.logger.warning(
                "agent.run.failed",
                extra={"run_id": str(context.run_id), "error": error},
            )

        context.metrics.latency_ms = (time.perf_counter() - start) * 1000
        output = self.final_output(graph, context) if graph.tasks else "No output."

        await self._publish_terminal(context)
        return AgentRunResult(
            run_id=str(context.run_id),
            state=self.state,
            output=output,
            goal_status=context.goal.status,
            metrics=context.metrics,
            graph=graph,
            reflection=reflection,
            evaluation=evaluation,
            error=error,
            reasoning_log=[
                str(v) for v in context.memory.scope_items("short_term").values()
            ],
        )

    async def _publish_terminal(self, context: AgentContext) -> None:
        if context.goal.status == GoalStatus.COMPLETED:
            await context.events.publish(
                GoalCompleted(run_id=context.run_id, agent_slug=self.slug)
            )
        elif context.goal.status == GoalStatus.FAILED:
            await context.events.publish(
                GoalFailed(
                    run_id=context.run_id,
                    agent_slug=self.slug,
                    reason="run failed",
                )
            )
        await context.events.publish(
            AgentStopped(
                run_id=context.run_id,
                agent_slug=self.slug,
                state=self.state.value,
            )
        )

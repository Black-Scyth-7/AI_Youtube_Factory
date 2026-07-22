"""Planning engine.

Decomposes a goal into a dependency graph of tasks. Planning is a hybrid of a
robust deterministic decomposition (so it always produces a valid, acyclic graph
— even offline) enriched by an LLM-generated outline. Supports sequential and
parallel subtasks, a dependency graph, dynamic replanning after failures, and
failure recovery by appending remediation tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.base.tasks import AgentTask, TaskGraph, TaskKind, TaskStatus

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext
    from app.agents.base.goals import Goal


@dataclass(slots=True)
class Plan:
    """A produced plan: the task graph plus the rationale behind it."""

    graph: TaskGraph
    rationale: str = ""
    outline: list[str] = field(default_factory=list)


class Planner:
    """Turns a goal into an executable :class:`TaskGraph`."""

    async def plan(self, goal: Goal, context: AgentContext) -> TaskGraph:
        """Decompose ``goal`` into a task graph."""
        plan = await self.build_plan(goal, context)
        context.memory.remember("agent", "plan_rationale", plan.rationale)
        return plan.graph

    async def build_plan(self, goal: Goal, context: AgentContext) -> Plan:
        """Produce a :class:`Plan` with rationale and outline."""
        outline = await self._outline(goal, context)
        graph = self._decompose(goal, context, outline)
        rationale = (
            f"Decomposed '{goal.objective}' into {len(graph.tasks)} tasks "
            f"({len(outline)} outline steps)."
        )
        return Plan(graph=graph, rationale=rationale, outline=outline)

    async def replan(
        self, goal: Goal, graph: TaskGraph, context: AgentContext
    ) -> TaskGraph:
        """Repair a graph after failures by appending recovery tasks."""
        failed = [t for t in graph.tasks if t.status == TaskStatus.FAILED]
        if not failed:
            return graph
        for task in failed:
            recovery = AgentTask(
                description=f"Recover from failed task: {task.description}",
                kind=TaskKind.REASON,
                depends_on=[d for d in task.depends_on if graph.get(d) is not None],
                payload={"recovers": task.key, "reason": task.error or "unknown"},
            )
            graph.add(recovery)
            task.log(f"replanned: added recovery task {recovery.key}")
        context.logger.info(
            "agent.replan",
            extra={"failed": len(failed), "run_id": str(context.run_id)},
        )
        return graph

    async def _outline(self, goal: Goal, context: AgentContext) -> list[str]:
        """Ask the LLM for a short step outline (best-effort, offline-safe)."""
        prompt = (
            f"Break this goal into 3-6 short imperative steps, one per line:\n"
            f"{goal.objective}"
        )
        try:
            text = await context.complete(prompt, system="You are a planning assistant.")
        except Exception:
            return []
        steps = [
            line.strip("-*0123456789. ").strip()
            for line in text.splitlines()
            if line.strip()
        ]
        return [s for s in steps if s][:6]

    def _decompose(
        self, goal: Goal, context: AgentContext, outline: list[str]
    ) -> TaskGraph:
        """Build the deterministic task graph (always valid + acyclic)."""
        graph = TaskGraph()

        understand = AgentTask(
            description=f"Understand the goal: {goal.objective}",
            kind=TaskKind.REASON,
            key="understand",
        )
        graph.add(understand)

        # One work task per success criterion, else per outline step, else one.
        work_keys: list[str] = []
        sources: list[str]
        if goal.success_criteria:
            sources = [c.description for c in goal.success_criteria]
        elif outline:
            sources = outline
        else:
            sources = [f"Work towards: {goal.objective}"]

        limit = max(1, context.config.max_tasks - 2)
        for index, description in enumerate(sources[:limit]):
            key = f"work_{index}"
            graph.add(
                AgentTask(
                    description=description,
                    kind=TaskKind.REASON,
                    key=key,
                    depends_on=["understand"],
                )
            )
            work_keys.append(key)

        graph.add(
            AgentTask(
                description=(f"Synthesize the final result for: {goal.objective}"),
                kind=TaskKind.LLM,
                key="synthesize",
                depends_on=work_keys or ["understand"],
                payload={"expected_output": goal.expected_output or ""},
            )
        )
        return graph

"""Reasoning engine.

Implements the structured reasoning pipeline:

    Understand Goal -> Gather Context -> Plan -> Select Tools -> Execute
    -> Evaluate -> Reflect -> Improve

The reasoner produces a :class:`ReasoningTrace` for a task: what it understood,
the context it gathered (memory + knowledge), the approach it will take, and any
tool it intends to call. It reasons through the Phase 04 LLM framework and
degrades gracefully offline (the trace is still well-formed with the mock
provider).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext
    from app.agents.base.tasks import AgentTask


class ReasoningStage(StrEnum):
    """Stages of the reasoning pipeline."""

    UNDERSTAND = "understand"
    GATHER_CONTEXT = "gather_context"
    PLAN = "plan"
    SELECT_TOOLS = "select_tools"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    REFLECT = "reflect"
    IMPROVE = "improve"


@dataclass(slots=True)
class ReasoningStep:
    """A single reasoning step."""

    stage: ReasoningStage
    content: str


@dataclass(slots=True)
class ReasoningTrace:
    """The structured reasoning produced for a task."""

    task_key: str
    thought: str = ""
    selected_tool: str | None = None
    tool_arguments: dict[str, str] = field(default_factory=dict)
    steps: list[ReasoningStep] = field(default_factory=list)

    def add(self, stage: ReasoningStage, content: str) -> None:
        self.steps.append(ReasoningStep(stage=stage, content=content))


class Reasoner:
    """Produces structured reasoning for a task via the LLM framework."""

    async def reason(self, task: AgentTask, context: AgentContext) -> ReasoningTrace:
        """Reason about how to accomplish ``task`` and return a trace."""
        trace = ReasoningTrace(task_key=task.key)

        trace.add(
            ReasoningStage.UNDERSTAND,
            f"Goal: {context.goal.objective} | Task: {task.description}",
        )

        knowledge = context.knowledge.search(task.description, limit=3)
        policies = context.knowledge.policies()
        if knowledge or policies:
            trace.add(
                ReasoningStage.GATHER_CONTEXT,
                f"{len(knowledge)} knowledge hits, {len(policies)} policies",
            )

        available = ", ".join(t.name for t in context.tools.list_tools()) or "none"
        trace.add(ReasoningStage.SELECT_TOOLS, f"Available tools: {available}")

        prompt = self._build_prompt(task, context, knowledge)
        system = self._system_prompt(context)
        thought = await context.complete(prompt, system=system)
        trace.thought = thought
        trace.add(ReasoningStage.PLAN, thought)

        context.memory.remember("short_term", f"reasoning:{task.key}", thought)
        return trace

    def _system_prompt(self, context: AgentContext) -> str:
        instructions = context.config.instructions or (
            "You are a capable autonomous agent. Reason concisely and "
            "practically about how to accomplish the task."
        )
        policies = context.knowledge.policies()
        if policies:
            instructions += "\n\nHonor these policies:\n" + "\n".join(
                f"- {p}" for p in policies
            )
        return instructions

    def _build_prompt(
        self, task: AgentTask, context: AgentContext, knowledge: list[str]
    ) -> str:
        parts = [
            f"Overall goal: {context.goal.objective}",
            f"Current task: {task.description}",
        ]
        if context.goal.constraints:
            parts.append("Constraints: " + "; ".join(context.goal.constraints))
        if knowledge:
            parts.append("Relevant knowledge:\n" + "\n".join(f"- {k}" for k in knowledge))
        parts.append("Explain briefly how to accomplish this task.")
        return "\n\n".join(parts)

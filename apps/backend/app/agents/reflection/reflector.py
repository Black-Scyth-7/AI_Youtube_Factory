"""Reflection engine.

After execution, the reflector analyzes what happened: which tasks failed, what
mistakes were made, and what lessons should carry forward. Lessons are stored in
agent memory so future runs benefit. Reflection is best-effort and never fails
the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.agents.base.tasks import TaskGraph, TaskStatus

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext


@dataclass(slots=True)
class Reflection:
    """The outcome of a reflection pass."""

    summary: str = ""
    mistakes: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)


class Reflector:
    """Analyzes a completed run and produces lessons."""

    async def reflect(self, graph: TaskGraph, context: AgentContext) -> Reflection:
        """Reflect on ``graph`` and return a :class:`Reflection`."""
        succeeded = [t for t in graph.tasks if t.status == TaskStatus.SUCCEEDED]
        failed = [t for t in graph.tasks if t.status == TaskStatus.FAILED]

        reflection = Reflection(
            summary=(
                f"{len(succeeded)}/{len(graph.tasks)} tasks succeeded, "
                f"{len(failed)} failed."
            )
        )
        for task in failed:
            reflection.mistakes.append(
                f"Task '{task.description}' failed: {task.error or 'unknown error'}"
            )

        prompt = self._build_prompt(len(succeeded), len(failed), context)
        try:
            text = await context.complete(
                prompt, system="You are a reflective post-mortem assistant."
            )
            for line in text.splitlines():
                cleaned = line.strip("-*0123456789. ").strip()
                if cleaned:
                    reflection.lessons.append(cleaned)
        except Exception as exc:
            context.logger.warning("agent.reflect.llm_failed", extra={"error": str(exc)})

        if failed:
            reflection.improvements.append(
                "Add validation or fallback handling for the failed tasks."
            )

        # Persist lessons so future runs benefit.
        existing = context.memory.recall("agent", "lessons") or []
        context.memory.remember("agent", "lessons", [*existing, *reflection.lessons][:50])
        return reflection

    def _build_prompt(self, succeeded: int, failed: int, context: AgentContext) -> str:
        return (
            f"Goal: {context.goal.objective}\n"
            f"Succeeded: {succeeded} tasks, Failed: {failed} tasks.\n\n"
            "List 2-4 concise lessons to improve future runs, one per line."
        )

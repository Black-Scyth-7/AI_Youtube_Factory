"""ReasoningService — one-off structured reasoning.

Runs the reasoning pipeline for a single ad-hoc task within an objective and
returns the trace, without a full agent run. Useful for previews and debugging.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.context import AgentContext
from app.agents.base.goals import Goal
from app.agents.base.identity import AgentIdentity
from app.agents.base.tasks import AgentTask
from app.agents.reasoning.reasoner import Reasoner


@dataclass(slots=True)
class ReasoningResult:
    """The result of a one-off reasoning pass."""

    task: str
    thought: str
    steps: list[dict[str, str]]


class ReasoningService:
    """Produces a reasoning trace for a single task."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._reasoner = Reasoner()

    async def reason(
        self,
        objective: str,
        task_description: str,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> ReasoningResult:
        goal = Goal(objective=objective)
        context = AgentContext(
            identity=AgentIdentity(name="Reasoner", slug="reasoner"),
            goal=goal,
            organization_id=organization_id,
        )
        task = AgentTask(description=task_description)
        trace = await self._reasoner.reason(task, context)
        return ReasoningResult(
            task=task_description,
            thought=trace.thought,
            steps=[
                {"stage": step.stage.value, "content": step.content}
                for step in trace.steps
            ],
        )

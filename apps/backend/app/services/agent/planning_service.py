"""PlanningService — preview a plan without executing it.

Lets callers see how an agent would decompose a goal (task graph + rationale +
outline) before committing to a run. Uses the same :class:`Planner` the runtime
uses, so the preview matches execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.context import AgentContext
from app.agents.base.goals import Goal
from app.agents.base.identity import AgentIdentity
from app.agents.planner.planner import Planner


@dataclass(slots=True)
class PlanPreview:
    """A previewed plan."""

    objective: str
    rationale: str
    outline: list[str]
    tasks: list[dict[str, object]]


class PlanningService:
    """Produces plan previews for a goal."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._planner = Planner()

    async def preview(
        self,
        objective: str,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> PlanPreview:
        """Decompose ``objective`` into a plan without running it."""
        goal = Goal(objective=objective)
        context = AgentContext(
            identity=AgentIdentity(name="Planner", slug="planner"),
            goal=goal,
            organization_id=organization_id,
            user_id=user_id,
        )
        plan = await self._planner.build_plan(goal, context)
        return PlanPreview(
            objective=objective,
            rationale=plan.rationale,
            outline=plan.outline,
            tasks=[
                {
                    "key": task.key,
                    "description": task.description,
                    "kind": task.kind.value,
                    "depends_on": task.depends_on,
                }
                for task in plan.graph.topological_order()
            ],
        )

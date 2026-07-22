"""AgentWorkflowService — persist and read agent workflow runs.

Records executions of the in-process :class:`AgentWorkflow` step engine so the
workflow viewer can render step timelines. Named distinctly from the Phase 03
``WorkflowService`` (persisted graph engine) which it complements.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows.workflow import WorkflowResult
from app.models.agent import WorkflowRun
from app.repositories.agent import WorkflowRunRepository


class AgentWorkflowService:
    """Persists and reads agent workflow runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runs = WorkflowRunRepository(session)

    async def record(
        self,
        result: WorkflowResult,
        *,
        name: str,
        run_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Persist a finished workflow run."""
        return await self.runs.add(
            WorkflowRun(
                organization_id=organization_id,
                agent_id=agent_id,
                run_id=run_id,
                name=name,
                status="succeeded" if result.completed else "failed",
                completed=result.completed,
                steps=[
                    {
                        "name": step.name,
                        "status": step.status.value,
                        "error": step.error,
                    }
                    for step in result.steps
                ],
                context={k: str(v) for k, v in result.context.items()},
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

    async def get_or_none(self, workflow_run_id: uuid.UUID) -> WorkflowRun | None:
        return await self.runs.get(workflow_run_id)

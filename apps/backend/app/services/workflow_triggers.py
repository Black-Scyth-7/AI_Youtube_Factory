"""Workflow triggers: what starts a run.

Three kinds — manual, schedule (cron), and event. The cron matcher is the one
already used by the agent scheduler rather than a second implementation, so both
subsystems agree on what a expression means.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scheduler.scheduler import cron_matches
from app.exceptions.base import NotFoundError, ValidationError
from app.models.domain_enums import TriggerKind
from app.models.workflow import WorkflowExecution, WorkflowTrigger
from app.repositories.base import BaseRepository
from app.services.workflow import WorkflowService


class WorkflowTriggerRepository(BaseRepository[WorkflowTrigger]):
    model = WorkflowTrigger

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> list[WorkflowTrigger]:
        stmt = self._base_query().where(WorkflowTrigger.workflow_id == workflow_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_active(self, kind: str) -> list[WorkflowTrigger]:
        stmt = self._base_query().where(
            WorkflowTrigger.kind == kind, WorkflowTrigger.is_active.is_(True)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_event(self, event_type: str) -> list[WorkflowTrigger]:
        stmt = select(WorkflowTrigger).where(
            WorkflowTrigger.kind == TriggerKind.EVENT.value,
            WorkflowTrigger.is_active.is_(True),
            WorkflowTrigger.event_type == event_type,
            WorkflowTrigger.deleted_at.is_(None),
        )
        return list((await self.session.execute(stmt)).scalars().all())


class WorkflowTriggerService:
    """Creates triggers and fires the ones that are due."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkflowTriggerRepository(session)
        self.workflows = WorkflowService(session)

    async def create(
        self,
        workflow_id: uuid.UUID,
        kind: str,
        *,
        cron: str | None = None,
        event_type: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> WorkflowTrigger:
        if kind not in set(TriggerKind):
            raise ValidationError(f"Unknown trigger kind: {kind}")
        if kind == TriggerKind.SCHEDULE.value and not cron:
            raise ValidationError("A schedule trigger needs a cron expression.")
        if kind == TriggerKind.EVENT.value and not event_type:
            raise ValidationError("An event trigger needs an event type.")

        trigger = WorkflowTrigger(
            workflow_id=workflow_id,
            kind=kind,
            cron=cron,
            event_type=event_type,
            config=config or {},
        )
        return await self.repo.add(trigger)

    async def due(self, moment: datetime | None = None) -> list[WorkflowTrigger]:
        """Schedule triggers whose cron matches ``moment``.

        Firing is recorded to the minute: cron has minute resolution, so a
        trigger already fired within the same minute is not returned again even
        if the poller runs several times.
        """
        now = moment or datetime.now(UTC)
        candidates = await self.repo.list_active(TriggerKind.SCHEDULE.value)
        result: list[WorkflowTrigger] = []
        for trigger in candidates:
            if not trigger.cron or not cron_matches(trigger.cron, now):
                continue
            last = trigger.last_fired_at
            if last is not None and last.replace(second=0, microsecond=0) == now.replace(
                second=0, microsecond=0
            ):
                continue
            result.append(trigger)
        return result

    async def fire(
        self, trigger: WorkflowTrigger, *, inputs: dict[str, Any] | None = None
    ) -> WorkflowExecution:
        """Run the trigger's workflow and stamp it as fired."""
        payload = {**trigger.config, **(inputs or {})}
        execution = await self.workflows.execute(trigger.workflow_id, inputs=payload)
        trigger.last_fired_at = datetime.now(UTC)
        await self.session.flush()
        return execution

    async def fire_due(self, moment: datetime | None = None) -> list[WorkflowExecution]:
        """Fire every schedule trigger that is due right now."""
        return [await self.fire(trigger) for trigger in await self.due(moment)]

    async def dispatch_event(
        self, event_type: str, payload: dict[str, Any] | None = None
    ) -> list[WorkflowExecution]:
        """Run every active workflow subscribed to ``event_type``."""
        triggers = await self.repo.list_for_event(event_type)
        return [await self.fire(t, inputs=payload) for t in triggers]

    async def set_active(self, trigger_id: uuid.UUID, *, active: bool) -> WorkflowTrigger:
        trigger = await self.repo.get(trigger_id)
        if trigger is None:
            raise NotFoundError("Trigger not found.")
        trigger.is_active = active
        await self.session.flush()
        return trigger

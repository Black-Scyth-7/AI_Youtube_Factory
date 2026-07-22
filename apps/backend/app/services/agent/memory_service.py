"""MemoryService — persist and read agent memory.

Bridges the in-process :class:`AgentMemoryStore` to durable storage. Snapshots a
run's scoped memory into rows and reads them back for the memory explorer.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory.memory import AgentMemoryStore
from app.models.agent import AgentMemoryRecord
from app.repositories.agent import AgentMemoryRepository


class MemoryService:
    """Persists and reads scoped agent memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.records = AgentMemoryRepository(session)

    async def snapshot(
        self,
        store: AgentMemoryStore,
        *,
        run_id: uuid.UUID,
        agent_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> int:
        """Persist a store's scoped memory; return the number of rows written."""
        written = 0
        for scope, items in store.snapshot().items():
            for key, value in items.items():
                await self.records.add(
                    AgentMemoryRecord(
                        organization_id=organization_id,
                        agent_id=agent_id,
                        run_id=run_id,
                        scope=scope,
                        key=str(key),
                        value={"value": value},
                        created_by=actor_id,
                        updated_by=actor_id,
                    )
                )
                written += 1
        return written

    async def list_for_run(self, run_id: uuid.UUID) -> list[AgentMemoryRecord]:
        return await self.records.list_for_run(run_id)

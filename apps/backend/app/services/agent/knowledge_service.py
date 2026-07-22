"""KnowledgeService — CRUD for knowledge documents + runtime base assembly.

Persists organization-scoped knowledge documents and assembles a runtime
:class:`KnowledgeBase` an agent consults during a run.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.knowledge.knowledge import (
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeKind,
)
from app.exceptions.base import NotFoundError
from app.models.agent import KnowledgeDocument
from app.repositories.agent import KnowledgeDocumentRepository


class KnowledgeService:
    """Manages knowledge documents and builds runtime knowledge bases."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.documents = KnowledgeDocumentRepository(session)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        title: str,
        content: str,
        actor_id: uuid.UUID,
        kind: str = "fact",
        tags: list[str] | None = None,
        agent_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> KnowledgeDocument:
        return await self.documents.add(
            KnowledgeDocument(
                organization_id=organization_id,
                agent_id=agent_id,
                title=title,
                content=content,
                kind=kind,
                tags=tags or [],
                source=source,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

    async def list_for_org(self, organization_id: uuid.UUID) -> list[KnowledgeDocument]:
        return await self.documents.list_for_org(organization_id)

    async def get_or_404(self, document_id: uuid.UUID) -> KnowledgeDocument:
        doc = await self.documents.get(document_id)
        if doc is None or doc.deleted_at is not None:
            raise NotFoundError("Knowledge document not found.")
        return doc

    async def delete(self, document_id: uuid.UUID) -> None:
        doc = await self.get_or_404(document_id)
        await self.documents.soft_delete(doc)

    async def build_base(self, organization_id: uuid.UUID | None) -> KnowledgeBase:
        """Build a runtime :class:`KnowledgeBase` from stored documents."""
        base = KnowledgeBase()
        if organization_id is None:
            return base
        for doc in await self.documents.list_for_org(organization_id):
            try:
                kind = KnowledgeKind(doc.kind)
            except ValueError:
                kind = KnowledgeKind.FACT
            base.add(
                KnowledgeEntry(
                    title=doc.title,
                    content=doc.content,
                    kind=kind,
                    tags=tuple(doc.tags),
                )
            )
        return base

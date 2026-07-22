"""Conversation persistence service.

Creates conversations, appends messages, and rebuilds the runtime
:class:`Conversation` from stored history so a turn can continue an existing
thread.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.conversation import Conversation as RuntimeConversation
from app.core.llm.messages import Message, Role
from app.exceptions.base import NotFoundError
from app.models.llm import Conversation, ConversationMessage
from app.repositories.llm import (
    ConversationMessageRepository,
    ConversationRepository,
)


class ConversationService:
    """Manages persisted conversations and their messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = ConversationMessageRepository(session)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID,
        model: str | None = None,
        system: str | None = None,
        title: str | None = None,
    ) -> Conversation:
        return await self.conversations.add(
            Conversation(
                organization_id=organization_id,
                user_id=actor_id,
                model=model or settings.llm_default_model,
                system=system,
                title=title,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

    async def get_or_404(self, conversation_id: uuid.UUID) -> Conversation:
        record = await self.conversations.get(conversation_id)
        if record is None or record.deleted_at is not None:
            raise NotFoundError("Conversation not found.")
        return record

    async def append(
        self,
        *,
        conversation_id: uuid.UUID,
        role: Role,
        content: str,
        actor_id: uuid.UUID | None = None,
        tokens: int = 0,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ConversationMessage:
        sequence = await self.messages.next_sequence(conversation_id)
        return await self.messages.add(
            ConversationMessage(
                conversation_id=conversation_id,
                sequence=sequence,
                role=role.value,
                content=content,
                tool_calls=tool_calls or [],
                tokens=tokens,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

    async def load_runtime(self, conversation_id: uuid.UUID) -> RuntimeConversation:
        """Rebuild the in-memory conversation from stored messages."""
        record = await self.get_or_404(conversation_id)
        stored = await self.messages.list_for_conversation(conversation_id)
        runtime = RuntimeConversation(id=record.id, system=record.system)
        for message in stored:
            runtime.add(Message(role=Role(message.role), content=message.content))
        return runtime

"""LLMService — the application entry point for AI capabilities.

All AI features go through this service, which delegates to the
:class:`LLMManager` (provider + cache + retry + limits + metrics), persists
conversation turns, records accounting, and offers structured-output parsing
with a validation-retry loop. No feature calls a provider or the Anthropic SDK
directly.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.exceptions import StructuredOutputError
from app.core.llm.manager import ChatOutcome, LLMManager, get_llm_manager
from app.core.llm.messages import ChatRequest, Message, Role
from app.core.llm.schemas import json_schema_for, parse_structured
from app.core.llm.streaming import StreamEvent
from app.services.llm.accounting import AccountingService
from app.services.llm.conversation_service import ConversationService

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMService:
    """High-level orchestration for chat, structured output, and streaming."""

    def __init__(
        self, session: AsyncSession, *, manager: LLMManager | None = None
    ) -> None:
        self.session = session
        self.manager = manager or get_llm_manager()
        self.accounting = AccountingService(session)
        self.conversations = ConversationService(session)

    def _build_request(
        self,
        messages: list[Message],
        *,
        model: str | None,
        system: str | None,
        max_tokens: int | None,
        **kwargs: object,
    ) -> ChatRequest:
        return ChatRequest(
            messages=messages,
            model=model or settings.llm_default_model,
            system=system or settings.llm_system_prompt,
            max_tokens=max_tokens or settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            top_p=settings.llm_top_p,
            top_k=settings.llm_top_k,
            thinking=settings.llm_thinking == "adaptive",
            **kwargs,  # type: ignore[arg-type]
        )

    async def chat(
        self,
        messages: list[Message],
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        provider: str | None = None,
    ) -> ChatOutcome:
        """Run a chat turn, record accounting, and optionally persist history."""
        request = self._build_request(
            messages, model=model, system=system, max_tokens=max_tokens
        )
        outcome = await self.manager.chat(
            request,
            provider_slug=provider,
            rate_limit_key=str(organization_id or "global"),
        )
        await self.accounting.record(
            outcome,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if conversation_id is not None and messages:
            await self.conversations.append(
                conversation_id=conversation_id,
                role=Role.USER,
                content=messages[-1].content,
                actor_id=user_id,
                tokens=outcome.response.usage.input_tokens,
            )
            await self.conversations.append(
                conversation_id=conversation_id,
                role=Role.ASSISTANT,
                content=outcome.response.content,
                actor_id=user_id,
                tokens=outcome.response.usage.output_tokens,
            )
        return outcome

    async def chat_structured(
        self,
        messages: list[Message],
        response_model: type[ModelT],
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        model: str | None = None,
        system: str | None = None,
        max_retries: int = 1,
    ) -> ModelT:
        """Return a validated Pydantic model, retrying once on malformed output."""
        schema = json_schema_for(response_model)
        attempt = 0
        conversation = list(messages)
        while True:
            request = self._build_request(
                conversation,
                model=model,
                system=system,
                max_tokens=None,
                response_schema=schema,
            )
            outcome = await self.manager.chat(
                request, rate_limit_key=str(organization_id or "global")
            )
            await self.accounting.record(
                outcome, organization_id=organization_id, user_id=user_id
            )
            try:
                return parse_structured(outcome.response.content, response_model)
            except StructuredOutputError:
                attempt += 1
                if attempt > max_retries:
                    raise
                conversation = [
                    *conversation,
                    outcome.response.to_message(),
                    Message.user(
                        "Your previous response was not valid JSON for the schema. "
                        "Respond again with ONLY a valid JSON object."
                    ),
                ]

    async def stream(
        self,
        messages: list[Message],
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        provider: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat turn, recording accounting when the final event arrives."""
        request = self._build_request(
            messages, model=model, system=system, max_tokens=max_tokens
        )
        async for event in self.manager.stream(
            request,
            provider_slug=provider,
            rate_limit_key=str(organization_id or "global"),
        ):
            if event.response is not None:
                await self.accounting.record(
                    ChatOutcome(
                        response=event.response,
                        provider=provider or settings.llm_default_provider,
                        latency_ms=0.0,
                        cost_usd=0.0,
                    ),
                    organization_id=organization_id,
                    user_id=user_id,
                    streamed=True,
                )
            yield event

"""LLM framework API routes.

Chat / streaming / structured generation, prompt management, conversations,
model catalog, usage and cost reporting, tools, and provider health. Org-scoped
operations enforce RBAC permissions; chat is authenticated and accounted.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.llm import available_providers, get_provider
from app.core.llm.messages import Message, Role
from app.core.llm.models import list_models
from app.core.llm.tools import Tool, ToolRegistry
from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.llm import (
    ChatMessageIn,
    ChatRequestIn,
    ChatResponseOut,
    ConversationCreateIn,
    ConversationMessageOut,
    ConversationOut,
    CostSummaryOut,
    ModelOut,
    PromptCreateIn,
    PromptRenderIn,
    PromptRenderOut,
    PromptTemplateOut,
    PromptVersionIn,
    ProviderHealthOut,
    ToolSchemaOut,
    UsageOut,
    UsageSummaryOut,
)
from app.services.llm import (
    ConversationService,
    CostService,
    LLMService,
    PromptService,
)
from app.services.rbac import RBACService

router = APIRouter(prefix="/llm", tags=["llm"])

# Example tool registry (future agents register real tools here).
_tools = ToolRegistry()


async def _echo_tool(args: dict[str, Any]) -> str:
    return f"echo: {args.get('text', '')}"


_tools.register(
    Tool(
        name="echo",
        description="Echo back the provided text.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=_echo_tool,
    )
)


def _to_messages(items: list[ChatMessageIn]) -> list[Message]:
    return [Message(role=Role(m.role), content=m.content) for m in items]


# -- Chat / streaming ----------------------------------------------------
@router.post("/chat", response_model=ChatResponseOut)
async def chat(
    body: ChatRequestIn, user: CurrentUser, session: DbSession
) -> ChatResponseOut:
    """Run a single chat completion (accounted, cached, retried)."""
    if body.organization_id is not None and not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, body.organization_id, "agent.run"
        )
    outcome = await LLMService(session).chat(
        _to_messages(body.messages),
        organization_id=body.organization_id,
        user_id=user.id,
        conversation_id=body.conversation_id,
        model=body.model,
        system=body.system,
        max_tokens=body.max_tokens,
        provider=body.provider,
    )
    r = outcome.response
    return ChatResponseOut(
        content=r.content,
        model=r.model,
        provider=outcome.provider,
        stop_reason=r.stop_reason.value,
        usage=UsageOut(
            input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens,
            total_tokens=r.usage.total_tokens,
            cache_read_tokens=r.usage.cache_read_tokens,
        ),
        cost_usd=outcome.cost_usd,
        latency_ms=outcome.latency_ms,
        cache_hit=outcome.cache_hit,
    )


@router.post("/stream")
async def stream(
    body: ChatRequestIn, user: CurrentUser, session: DbSession
) -> StreamingResponse:
    """Stream a chat completion as Server-Sent Events."""

    async def event_source() -> AsyncIterator[str]:
        async for event in LLMService(session).stream(
            _to_messages(body.messages),
            organization_id=body.organization_id,
            user_id=user.id,
            model=body.model,
            system=body.system,
            provider=body.provider,
        ):
            yield f"data: {event.to_sse()}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


# -- Catalog / health ----------------------------------------------------
@router.get("/models", response_model=list[ModelOut])
async def models(_: CurrentUser) -> list[ModelOut]:
    return [
        ModelOut(
            id=m.id,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output=m.max_output,
            input_price_per_mtok=m.input_price_per_mtok,
            output_price_per_mtok=m.output_price_per_mtok,
            supports_tools=m.supports_tools,
            supports_streaming=m.supports_streaming,
        )
        for m in list_models()
    ]


@router.get("/health", response_model=list[ProviderHealthOut])
async def health(_: CurrentUser) -> list[ProviderHealthOut]:
    results: list[ProviderHealthOut] = []
    for slug in available_providers():
        healthy = await get_provider(slug).health_check()
        results.append(ProviderHealthOut(provider=slug, healthy=healthy))
    return results


@router.get("/tools", response_model=list[ToolSchemaOut])
async def tools(_: CurrentUser) -> list[ToolSchemaOut]:
    return [
        ToolSchemaOut(
            name=s["name"], description=s["description"], input_schema=s["input_schema"]
        )
        for s in _tools.schemas()
    ]


# -- Prompts -------------------------------------------------------------
@router.post("/prompts", response_model=PromptTemplateOut, status_code=201)
async def create_prompt(
    body: PromptCreateIn, user: CurrentUser, session: DbSession
) -> PromptTemplateOut:
    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, body.organization_id, "prompt.edit"
        )
    template, _ = await PromptService(session).create_template(
        organization_id=body.organization_id,
        name=body.name,
        template=body.template,
        actor_id=user.id,
        category=body.category,
        description=body.description,
        variables=[v.model_dump() for v in body.variables],
        tags=body.tags,
    )
    return PromptTemplateOut.model_validate(template)


@router.post(
    "/prompts/{template_id}/versions", response_model=PromptTemplateOut, status_code=201
)
async def add_prompt_version(
    template_id: uuid.UUID,
    body: PromptVersionIn,
    user: CurrentUser,
    session: DbSession,
) -> PromptTemplateOut:
    service = PromptService(session)
    await service.add_version(
        template_id=template_id,
        template=body.template,
        actor_id=user.id,
        variables=[v.model_dump() for v in body.variables],
    )
    template = await service.templates.get(template_id)
    return PromptTemplateOut.model_validate(template)


@router.post("/prompts/{template_id}/render", response_model=PromptRenderOut)
async def render_prompt(
    template_id: uuid.UUID,
    body: PromptRenderIn,
    _: CurrentUser,
    session: DbSession,
) -> PromptRenderOut:
    rendered = await PromptService(session).render(
        template_id=template_id, context=body.context, version=body.version
    )
    return PromptRenderOut(rendered=rendered)


@router.post("/prompts/{template_id}/rollback", response_model=MessageResponse)
async def rollback_prompt(
    template_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    to_version: int = Query(..., ge=1),
) -> MessageResponse:
    version = await PromptService(session).rollback(
        template_id=template_id, to_version=to_version, actor_id=user.id
    )
    return MessageResponse(
        message=f"Rolled back to a new version {version.version_number}."
    )


# -- Conversations -------------------------------------------------------
@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreateIn, user: CurrentUser, session: DbSession
) -> ConversationOut:
    convo = await ConversationService(session).create(
        organization_id=body.organization_id,
        actor_id=user.id,
        model=body.model,
        system=body.system,
        title=body.title,
    )
    return ConversationOut.model_validate(convo)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageOut],
)
async def conversation_messages(
    conversation_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> list[ConversationMessageOut]:
    service = ConversationService(session)
    await service.get_or_404(conversation_id)
    messages = await service.messages.list_for_conversation(conversation_id)
    return [ConversationMessageOut.model_validate(m) for m in messages]


# -- Usage / costs -------------------------------------------------------
@router.get("/usage", response_model=UsageSummaryOut)
async def usage(
    organization_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    start: str = Query(...),
    end: str = Query(...),
) -> UsageSummaryOut:
    from datetime import date

    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, organization_id, "analytics.read"
        )
    summary = await CostService(session).usage_summary(
        organization_id=organization_id,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
    )
    return UsageSummaryOut(**asdict(summary))


@router.get("/costs", response_model=CostSummaryOut)
async def costs(
    organization_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    start: str = Query(...),
    end: str = Query(...),
) -> CostSummaryOut:
    from datetime import date

    if not user.is_superuser:
        await RBACService(session).require_permission(
            user.id, organization_id, "analytics.read"
        )
    summary = await CostService(session).cost_summary(
        organization_id=organization_id,
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
    )
    return CostSummaryOut(**asdict(summary))

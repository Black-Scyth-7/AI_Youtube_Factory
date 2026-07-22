"""ToolService — the agent tool catalog.

Exposes the built-in runtime tools and any organization-defined tool definitions.
Runtime tools carry executable code; DB tool definitions are metadata used for
discovery and display. New tools (including YouTube-specific ones in later
phases) register the same way.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.builtins import HTTPRequestTool, default_tools
from app.models.agent import AgentToolDefinition
from app.repositories.agent import AgentToolRepository


@dataclass(slots=True)
class ToolInfo:
    """A tool exposed in the catalog."""

    name: str
    description: str
    input_schema: dict[str, Any]
    mutating: bool
    builtin: bool


def builtin_tools() -> list[ToolInfo]:
    """Return the built-in runtime tool catalog."""
    tools = [*default_tools(), HTTPRequestTool()]
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            input_schema=t.parameters,
            mutating=t.mutating,
            builtin=True,
        )
        for t in tools
    ]


class ToolService:
    """Lists built-in and organization-defined tools."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tools = AgentToolRepository(session)

    async def catalog(self, organization_id: uuid.UUID | None = None) -> list[ToolInfo]:
        """Return built-in tools plus enabled DB-defined tools."""
        catalog = builtin_tools()
        for row in await self.tools.list_enabled():
            catalog.append(
                ToolInfo(
                    name=row.name,
                    description=row.description,
                    input_schema=row.input_schema,
                    mutating=row.mutating,
                    builtin=row.is_builtin,
                )
            )
        return catalog

    async def register(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        actor_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        mutating: bool = False,
        category: str = "general",
    ) -> AgentToolDefinition:
        return await self.tools.add(
            AgentToolDefinition(
                organization_id=organization_id,
                name=name,
                description=description,
                input_schema=input_schema,
                mutating=mutating,
                category=category,
                enabled=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

"""Assistant agent — a general-purpose helper.

Registers the safe default tool set and a little baseline knowledge, then relies
on the standard plan -> reason -> execute -> reflect -> evaluate lifecycle. This
is the template most product agents (support, research, coding) will start from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.base.agent import BaseAgent
from app.agents.knowledge.knowledge import KnowledgeEntry, KnowledgeKind
from app.agents.tools.builtins import default_tools

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext


class AssistantAgent(BaseAgent):
    """A general-purpose assistant with tools and baseline knowledge."""

    name = "Assistant Agent"
    slug = "assistant"
    description = "General-purpose assistant with tools and reflection."
    version = "1.0.0"
    capabilities = ("chat", "tools", "reasoning")
    tags = ("example", "general")
    category = "general"

    async def configure(self, context: AgentContext) -> None:
        for tool in default_tools():
            context.tools.register(tool)
        context.knowledge.add(
            KnowledgeEntry(
                title="Tone",
                content="Be concise, accurate, and helpful.",
                kind=KnowledgeKind.PREFERENCE,
                tags=("style",),
            )
        )
        context.knowledge.add(
            KnowledgeEntry(
                title="Safety",
                content="Never take destructive actions without explicit approval.",
                kind=KnowledgeKind.POLICY,
                tags=("safety",),
            )
        )

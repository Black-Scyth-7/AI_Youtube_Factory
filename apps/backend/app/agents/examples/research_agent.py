"""Research agent — a generic multi-step researcher.

Demonstrates goal decomposition into research sub-steps plus synthesis. It is
domain-agnostic (no YouTube specifics): the same agent can research a topic for
support, marketing, or content pipelines. Real web tools plug in via the tool
registry in a later phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.base.agent import BaseAgent
from app.agents.knowledge.knowledge import KnowledgeEntry, KnowledgeKind
from app.agents.tools.builtins import CurrentTimeTool, JSONParserTool

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext


class ResearchAgent(BaseAgent):
    """A generic research assistant that gathers, analyzes, and synthesizes."""

    name = "Research Agent"
    slug = "research"
    description = "Decomposes a research goal, gathers findings, and synthesizes."
    version = "1.0.0"
    capabilities = ("research", "analysis", "synthesis")
    tags = ("example", "research")
    category = "knowledge"

    async def configure(self, context: AgentContext) -> None:
        context.tools.register(CurrentTimeTool())
        context.tools.register(JSONParserTool())
        context.knowledge.add(
            KnowledgeEntry(
                title="Method",
                content=(
                    "Gather diverse sources, cross-check facts, and cite the "
                    "strongest evidence before concluding."
                ),
                kind=KnowledgeKind.RULE,
                tags=("research", "method"),
            )
        )
        context.config.max_iterations = 8

"""Echo agent — the minimal example.

Demonstrates the smallest possible concrete agent: it inherits the full
lifecycle and simply echoes a concise result. Useful as a smoke-test agent and a
template for new agents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.base.agent import BaseAgent
from app.agents.base.config import AgentConfig

if TYPE_CHECKING:
    from app.agents.base.context import AgentContext
    from app.agents.base.tasks import TaskGraph


class EchoAgent(BaseAgent):
    """A trivial agent that restates its goal as the result."""

    name = "Echo Agent"
    slug = "echo"
    description = "Restates the goal; a minimal example and smoke-test agent."
    version = "1.0.0"
    capabilities = ("echo",)
    tags = ("example", "test")
    category = "utility"

    async def configure(self, context: AgentContext) -> None:
        # Keep the run cheap and deterministic.
        context.config.reflection_enabled = False
        context.config.evaluation_enabled = True

    def final_output(self, graph: TaskGraph, context: AgentContext) -> str:
        return f"Echo: {context.goal.objective}"

    @staticmethod
    def default_config() -> AgentConfig:
        return AgentConfig(max_iterations=3, reflection_enabled=False)

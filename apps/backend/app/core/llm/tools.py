"""Tool-calling framework.

A ``Tool`` couples a JSON-schema declaration (sent to the model) with an async
handler (executed when the model calls it). A ``ToolRegistry`` resolves and
executes tool calls, validating arguments against the schema and capturing
results/errors. Future AI agents build their tool surface on this.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.messages import ToolCall, ToolResult
from app.logging import get_logger

logger = get_logger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(slots=True)
class Tool:
    """A callable tool exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema for the input object
    handler: ToolHandler

    def to_schema(self) -> dict[str, Any]:
        """Return the Anthropic tool definition for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def validate_arguments(self, arguments: dict[str, Any]) -> None:
        """Validate ``arguments`` against required fields of the schema."""
        required = self.parameters.get("required", [])
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments: {missing}")


class ToolRegistry:
    """Holds tools and executes model-issued tool calls."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, call: ToolCall) -> ToolResult:
        """Execute a tool call, returning a :class:`ToolResult`."""
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=f"Unknown tool: {call.name}",
                is_error=True,
            )
        try:
            tool.validate_arguments(call.arguments)
            output = await tool.handler(call.arguments)
            logger.info("llm.tool.executed", extra={"tool": call.name})
            return ToolResult(tool_call_id=call.id, content=output)
        except Exception as exc:
            logger.warning(
                "llm.tool.failed", extra={"tool": call.name, "error": str(exc)}
            )
            return ToolResult(
                tool_call_id=call.id, content=f"Tool error: {exc}", is_error=True
            )


@dataclass
class ToolExecutionRecord:
    """A record of a tool execution for auditing/observability."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

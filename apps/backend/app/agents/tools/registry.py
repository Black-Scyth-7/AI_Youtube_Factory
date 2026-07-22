"""Generic tool framework for agents.

An :class:`AgentTool` couples a JSON-schema declaration with an async
implementation and the full tool lifecycle the spec requires: ``validate`` /
``execute`` / ``rollback`` / ``describe`` / ``schema`` / ``health``. The
:class:`AgentToolRegistry` discovers tools, validates arguments, executes them,
and captures a structured :class:`ToolOutcome` (with timing and errors).

Agent tools bridge to the Phase 04 LLM tool-calling layer via
:meth:`AgentTool.to_llm_tool`, so the same tool can be offered to Claude.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.core.llm.tools import Tool as LLMTool
from app.logging import get_logger

logger = get_logger(__name__)


class ToolValidationError(ValueError):
    """Raised when tool arguments fail schema validation."""


@dataclass(slots=True)
class ToolOutcome:
    """The captured result of a tool execution."""

    tool_name: str
    arguments: dict[str, Any]
    output: str = ""
    success: bool = True
    error: str | None = None
    duration_ms: float = 0.0
    result: Any = None


class AgentTool(ABC):
    """Base class for a validated, reversible, describable tool."""

    name: str = ""
    description: str = ""
    #: JSON schema for the tool's argument object.
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    #: Whether calling this tool mutates external state (gates approval/rollback).
    mutating: bool = False

    def schema(self) -> dict[str, Any]:
        """Return the tool declaration (name + description + input schema)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def describe(self) -> str:
        """Return a human-readable one-line description."""
        return f"{self.name}: {self.description}"

    def validate(self, arguments: dict[str, Any]) -> None:
        """Validate ``arguments`` against required fields; raise on error."""
        required = self.parameters.get("required", [])
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ToolValidationError(
                f"{self.name}: missing required arguments {missing}"
            )

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Run the tool and return its textual result."""

    async def rollback(self, arguments: dict[str, Any], result: Any) -> None:
        """Undo a mutating execution. No-op for pure/read-only tools."""
        return None

    async def health(self) -> bool:
        """Return whether the tool is ready to run."""
        return True

    def to_llm_tool(self) -> LLMTool:
        """Adapt this tool to the Phase 04 LLM tool-calling interface."""
        return LLMTool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            handler=self.execute,
        )


@dataclass(slots=True)
class AgentToolRegistry:
    """Holds tools and runs them with validation + outcome capture."""

    _tools: dict[str, AgentTool] = field(default_factory=dict)

    def register(self, tool: AgentTool) -> None:
        """Register (or replace) a tool by name."""
        if not tool.name:
            raise ValueError("Tool must define a non-empty name.")
        self._tools[tool.name] = tool

    def register_all(self, tools: list[AgentTool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[AgentTool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    async def run(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        """Validate + execute ``name`` with ``arguments``, capturing the outcome."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutcome(
                tool_name=name,
                arguments=arguments,
                success=False,
                error=f"Unknown tool: {name}",
            )
        start = time.perf_counter()
        try:
            tool.validate(arguments)
            output = await tool.execute(arguments)
            duration = (time.perf_counter() - start) * 1000
            logger.info("agent.tool.executed", extra={"tool": name})
            return ToolOutcome(
                tool_name=name,
                arguments=arguments,
                output=output,
                success=True,
                duration_ms=duration,
                result=output,
            )
        except Exception as exc:
            duration = (time.perf_counter() - start) * 1000
            logger.warning("agent.tool.failed", extra={"tool": name, "error": str(exc)})
            return ToolOutcome(
                tool_name=name,
                arguments=arguments,
                success=False,
                error=str(exc),
                duration_ms=duration,
            )

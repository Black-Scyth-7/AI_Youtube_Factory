"""Built-in, provider-independent sample tools.

Generic tools every agent can use out of the box. They are deliberately small,
dependency-free, and safe to run offline (the HTTP tool is the only one that
touches the network and is disabled unless explicitly allowed). YouTube-specific
tools arrive in a later phase and register the same way.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from app.agents.tools.registry import AgentTool, ToolValidationError


class CurrentTimeTool(AgentTool):
    """Return the current UTC time in ISO-8601 format."""

    name = "current_time"
    description = "Get the current UTC date and time (ISO-8601)."
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> str:
        return datetime.now(UTC).isoformat()


class CalculatorTool(AgentTool):
    """Evaluate a basic arithmetic expression safely."""

    name = "calculator"
    description = "Evaluate a basic arithmetic expression (+ - * / and parentheses)."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }

    _ALLOWED: ClassVar[set[str]] = set("0123456789.+-*/() ")

    async def execute(self, arguments: dict[str, Any]) -> str:
        expression = str(arguments["expression"])
        if not expression or set(expression) - self._ALLOWED:
            raise ToolValidationError("Expression contains unsupported characters.")
        try:
            # Safe: the character allow-list above forbids names, calls, and
            # attribute access, leaving only arithmetic literals/operators.
            result = eval(expression, {"__builtins__": {}}, {})
        except (SyntaxError, ZeroDivisionError, ValueError) as exc:
            raise ToolValidationError(f"Invalid expression: {exc}") from exc
        return str(result)


class UUIDGeneratorTool(AgentTool):
    """Generate a random UUID4."""

    name = "uuid_generator"
    description = "Generate a random UUID4 string."
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> str:
        return str(uuid.uuid4())


class JSONParserTool(AgentTool):
    """Parse and re-serialize JSON, optionally reading a dotted path."""

    name = "json_parser"
    description = "Parse a JSON string; optionally extract a dotted key path."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "data": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["data"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            parsed: Any = json.loads(str(arguments["data"]))
        except json.JSONDecodeError as exc:
            raise ToolValidationError(f"Invalid JSON: {exc}") from exc
        path = arguments.get("path")
        if path:
            for part in str(path).split("."):
                if isinstance(parsed, dict) and part in parsed:
                    parsed = parsed[part]
                else:
                    raise ToolValidationError(f"Path not found: {path}")
        return json.dumps(parsed)


class NumberFormatTool(AgentTool):
    """Format a number to a fixed number of decimal places."""

    name = "number_format"
    description = "Format a number to N decimal places."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "decimals": {"type": "integer"},
        },
        "required": ["value"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            value = Decimal(str(arguments["value"]))
        except InvalidOperation as exc:
            raise ToolValidationError("Value is not a number.") from exc
        decimals = int(arguments.get("decimals", 2))
        return f"{value:.{decimals}f}"


class HTTPRequestTool(AgentTool):
    """Perform an HTTP GET request (network-gated; off by default).

    Marked ``mutating=False`` but network-touching — policies should keep this
    off the allow-list unless an agent genuinely needs outbound HTTP.
    """

    name = "http_request"
    description = "Perform an HTTP GET request and return the response body (text)."
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["url"],
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        import httpx

        url = str(arguments["url"])
        if not url.startswith(("http://", "https://")):
            raise ToolValidationError("URL must be http(s).")
        timeout = float(arguments.get("timeout", 10.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text[:10_000]


def default_tools() -> list[AgentTool]:
    """Return the safe, offline-friendly default tool set."""
    return [
        CurrentTimeTool(),
        CalculatorTool(),
        UUIDGeneratorTool(),
        JSONParserTool(),
        NumberFormatTool(),
    ]

"""Structured output parsing and recovery.

Parses model text into a validated Pydantic model. Includes best-effort recovery
for common malformed-JSON cases (code fences, leading/trailing prose) before
validation. Callers combine this with a validation-retry loop in the service
layer when the first parse fails.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.llm.exceptions import StructuredOutputError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> str:
    """Extract the most likely JSON payload from model text."""
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip()
    # Fall back to the outermost {...} or [...] span.
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    return text.strip()


def parse_structured[ModelT: BaseModel](text: str, model: type[ModelT]) -> ModelT:
    """Parse and validate ``text`` into ``model``, recovering from malformed JSON.

    Raises:
        StructuredOutputError: If parsing or validation ultimately fails.
    """
    candidate = extract_json(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            "Model output was not valid JSON.",
            details={"error": str(exc), "preview": candidate[:200]},
        ) from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(
            "Model output did not match the schema.",
            details={"errors": exc.errors(include_url=False)},
        ) from exc


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Return the JSON schema for a Pydantic model (for the API output_config)."""
    schema = model.model_json_schema()
    schema["additionalProperties"] = False
    return schema

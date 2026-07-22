"""Prompt engine.

Renders versioned, variable-driven prompt templates with Jinja2 in a sandboxed
environment. Supports declared variables (with required/optional + defaults),
validation of supplied context, reusable blocks via Jinja inheritance/includes
from an in-memory loader, and metadata/examples. Templates are stored in the
database (see the prompt models/service); this module is the pure rendering and
validation core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.core.llm.exceptions import PromptRenderError


@dataclass(slots=True)
class PromptVariable:
    """A declared template variable."""

    name: str
    required: bool = True
    default: Any = None
    description: str | None = None


@dataclass(slots=True)
class PromptSpec:
    """A renderable prompt definition."""

    name: str
    template: str
    variables: list[PromptVariable] = field(default_factory=list)
    version: int = 1
    category: str | None = None
    description: str | None = None
    examples: list[dict[str, Any]] = field(default_factory=list)


class PromptEngine:
    """Validates and renders prompt templates."""

    def __init__(self) -> None:
        self._env = SandboxedEnvironment(
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )

    def validate_context(
        self, spec: PromptSpec, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a resolved context, applying defaults and checking required vars."""
        resolved = dict(context)
        missing: list[str] = []
        for variable in spec.variables:
            if variable.name in resolved:
                continue
            if variable.default is not None:
                resolved[variable.name] = variable.default
            elif variable.required:
                missing.append(variable.name)
        if missing:
            raise PromptRenderError(
                "Missing required prompt variables.",
                details={"missing": missing, "prompt": spec.name},
            )
        return resolved

    def render(self, spec: PromptSpec, context: dict[str, Any] | None = None) -> str:
        """Render ``spec`` with ``context`` (validated against declared variables)."""
        resolved = self.validate_context(spec, context or {})
        try:
            template = self._env.from_string(spec.template)
            return template.render(**resolved)
        except TemplateError as exc:
            raise PromptRenderError(
                f"Failed to render prompt '{spec.name}': {exc}",
                details={"prompt": spec.name, "version": spec.version},
            ) from exc

    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render an ad-hoc template string."""
        try:
            return self._env.from_string(template).render(**context)
        except TemplateError as exc:
            raise PromptRenderError(f"Failed to render template: {exc}") from exc


_engine: PromptEngine | None = None


def get_prompt_engine() -> PromptEngine:
    """Return the process prompt-engine singleton."""
    global _engine
    if _engine is None:
        _engine = PromptEngine()
    return _engine

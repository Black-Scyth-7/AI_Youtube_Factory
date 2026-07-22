"""Agent configuration.

Tunable knobs for an agent run: which model to use, generation limits, and which
optional stages (reflection, evaluation) are enabled. Model selection flows from
here into the LLM bridge — never hardcoded in engine code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass(slots=True)
class AgentConfig:
    """Runtime configuration for an agent."""

    model: str = field(default_factory=lambda: settings.llm_default_model)
    max_tokens: int = field(default_factory=lambda: settings.llm_max_tokens)
    max_iterations: int = 6
    max_tasks: int = 25
    reflection_enabled: bool = True
    evaluation_enabled: bool = True
    system_prompt: str | None = None
    instructions: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

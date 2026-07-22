"""Claude provider entry point.

``ClaudeProvider`` is the Anthropic-backed provider used for all Claude models.
It is a thin alias over :class:`AnthropicProvider` so call sites can refer to
"Claude" while the implementation lives in the provider layer.
"""

from __future__ import annotations

from app.core.llm.providers.anthropic import AnthropicProvider


class ClaudeProvider(AnthropicProvider):
    """Anthropic Claude provider (alias of :class:`AnthropicProvider`)."""


__all__ = ["ClaudeProvider"]

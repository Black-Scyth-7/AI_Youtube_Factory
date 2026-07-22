"""Model catalog: capabilities and pricing.

Single source of truth for per-model metadata used by the framework — pricing
(for cost tracking), context/output limits, and capability flags. Model names
are never hardcoded in provider logic; callers pass a model id and this catalog
answers questions about it. Unknown models fall back to conservative defaults.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ModelInfo:
    """Metadata and pricing for a single model."""

    id: str
    display_name: str
    context_window: int
    max_output: int
    input_price_per_mtok: float
    output_price_per_mtok: float
    cache_read_price_per_mtok: float = 0.0
    supports_tools: bool = True
    supports_images: bool = True
    supports_streaming: bool = True
    # Opus 4.7+/Sonnet 5/Fable 5 reject temperature/top_p/top_k.
    accepts_sampling_params: bool = False
    adaptive_thinking_only: bool = True


# Prices in USD per 1M tokens (see the Claude API pricing reference).
_CATALOG: dict[str, ModelInfo] = {
    "claude-opus-4-8": ModelInfo(
        id="claude-opus-4-8",
        display_name="Claude Opus 4.8",
        context_window=1_000_000,
        max_output=128_000,
        input_price_per_mtok=5.0,
        output_price_per_mtok=25.0,
        cache_read_price_per_mtok=0.5,
    ),
    "claude-opus-4-7": ModelInfo(
        id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
        context_window=1_000_000,
        max_output=128_000,
        input_price_per_mtok=5.0,
        output_price_per_mtok=25.0,
        cache_read_price_per_mtok=0.5,
    ),
    "claude-sonnet-5": ModelInfo(
        id="claude-sonnet-5",
        display_name="Claude Sonnet 5",
        context_window=1_000_000,
        max_output=128_000,
        input_price_per_mtok=3.0,
        output_price_per_mtok=15.0,
        cache_read_price_per_mtok=0.3,
    ),
    "claude-haiku-4-5": ModelInfo(
        id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        context_window=200_000,
        max_output=64_000,
        input_price_per_mtok=1.0,
        output_price_per_mtok=5.0,
        cache_read_price_per_mtok=0.1,
        adaptive_thinking_only=False,
        accepts_sampling_params=True,
    ),
}

_DEFAULT = ModelInfo(
    id="unknown",
    display_name="Unknown model",
    context_window=200_000,
    max_output=8_192,
    input_price_per_mtok=5.0,
    output_price_per_mtok=25.0,
)


def get_model_info(model: str) -> ModelInfo:
    """Return metadata for ``model``, or conservative defaults if unknown."""
    from dataclasses import replace

    info = _CATALOG.get(model)
    return info if info is not None else replace(_DEFAULT, id=model)


def list_models() -> list[ModelInfo]:
    """Return all catalogued models."""
    return list(_CATALOG.values())


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost for a request/response."""
    info = get_model_info(model)
    return round(
        input_tokens / 1_000_000 * info.input_price_per_mtok
        + output_tokens / 1_000_000 * info.output_price_per_mtok,
        6,
    )

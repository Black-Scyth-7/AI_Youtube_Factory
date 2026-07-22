"""LLM framework exceptions (extend the app exception hierarchy)."""

from __future__ import annotations

from app.exceptions.base import AppError


class LLMError(AppError):
    """Base class for LLM framework errors."""

    status_code = 502
    code = "llm_error"
    message = "An LLM request failed."


class ProviderNotAvailableError(LLMError):
    """The requested provider is not registered or not configured."""

    status_code = 503
    code = "llm_provider_unavailable"
    message = "The requested LLM provider is not available."


class LLMRateLimitError(LLMError):
    """The provider (or our limiter) rejected the request for rate reasons."""

    status_code = 429
    code = "llm_rate_limited"
    message = "LLM rate limit exceeded."


class LLMTimeoutError(LLMError):
    """The provider did not respond in time."""

    status_code = 504
    code = "llm_timeout"
    message = "The LLM request timed out."


class StructuredOutputError(LLMError):
    """The model output could not be parsed/validated against the schema."""

    status_code = 422
    code = "llm_structured_output_error"
    message = "The model response did not match the expected schema."


class CircuitOpenError(LLMError):
    """The circuit breaker is open; the provider is being given time to recover."""

    status_code = 503
    code = "llm_circuit_open"
    message = "The LLM provider is temporarily unavailable (circuit open)."


class PromptRenderError(LLMError):
    """A prompt template failed to render or validate."""

    status_code = 422
    code = "prompt_render_error"
    message = "The prompt template could not be rendered."

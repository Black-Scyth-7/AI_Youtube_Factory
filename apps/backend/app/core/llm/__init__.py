"""LLM provider abstraction layer.

Application code depends only on this package. Concrete SDK calls live behind the
provider implementations registered with the factory (Phase 04+).
"""

from app.core.llm.base import BaseLLMClient
from app.core.llm.factory import create_llm_client, register_provider
from app.core.llm.interfaces import (
    CompletionRequest,
    CompletionResponse,
    LLMClient,
    LLMProvider,
    Message,
    TokenUsage,
)

__all__ = [
    "BaseLLMClient",
    "CompletionRequest",
    "CompletionResponse",
    "LLMClient",
    "LLMProvider",
    "Message",
    "TokenUsage",
    "create_llm_client",
    "register_provider",
]

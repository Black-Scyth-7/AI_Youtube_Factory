"""LLM provider framework.

Application and service code depends only on this package. All Anthropic SDK
access lives behind the provider layer (``providers/anthropic.py``); the
:class:`LLMManager` is the single orchestration entry point for chat/stream.

Legacy Phase 01 symbols (``BaseLLMClient``, ``create_llm_client``,
``interfaces``) are retained for backward compatibility. New code should use the
Phase 04 surface below and import message types from
``app.core.llm.messages``.
"""

from app.core.llm.base import BaseLLMClient, BaseLLMProvider
from app.core.llm.factory import create_llm_client
from app.core.llm.interfaces import LLMProvider
from app.core.llm.manager import (
    ChatOutcome,
    LLMManager,
    get_llm_manager,
    set_llm_manager,
)
from app.core.llm.prompts import PromptEngine, PromptSpec, get_prompt_engine
from app.core.llm.registry import (
    available_providers,
    get_provider,
    register_provider,
    reset_providers,
)

__all__ = [
    "BaseLLMClient",
    "BaseLLMProvider",
    "ChatOutcome",
    "LLMManager",
    "LLMProvider",
    "PromptEngine",
    "PromptSpec",
    "available_providers",
    "create_llm_client",
    "get_llm_manager",
    "get_prompt_engine",
    "get_provider",
    "register_provider",
    "reset_providers",
    "set_llm_manager",
]

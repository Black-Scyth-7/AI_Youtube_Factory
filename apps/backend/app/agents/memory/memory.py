"""Agent memory.

A scoped, in-process working memory that complements the Phase 04 conversation
memory. Scopes separate short-term working notes, task memory, per-agent memory,
and workspace-shared memory. Conversation history reuses the Phase 04
:class:`WindowMemory` for token-budgeted trimming and optional summarization.

Durable/vector memory plugs in behind the ``MemoryStore`` protocol in a later
phase; this class is the offline-friendly default.
"""

from __future__ import annotations

from typing import Any

from app.core.llm.memory import Summarizer, WindowMemory
from app.core.llm.messages import Message


class MemoryScope:
    """Well-known memory scope names."""

    SHORT_TERM = "short_term"
    TASK = "task"
    AGENT = "agent"
    WORKSPACE = "workspace"


class AgentMemoryStore:
    """Scoped key/value working memory plus a trimmed conversation buffer."""

    def __init__(
        self,
        *,
        max_context_tokens: int = 8000,
        summarizer: Summarizer | None = None,
    ) -> None:
        self._scopes: dict[str, dict[str, Any]] = {}
        self._messages: list[Message] = []
        self._window = WindowMemory(max_tokens=max_context_tokens, summarizer=summarizer)

    # -- Key/value scopes -------------------------------------------------
    def remember(self, scope: str, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` in ``scope``."""
        self._scopes.setdefault(scope, {})[key] = value

    def recall(self, scope: str, key: str) -> Any:
        """Return a stored value, or ``None`` if absent."""
        return self._scopes.get(scope, {}).get(key)

    def forget(self, scope: str, key: str) -> None:
        self._scopes.get(scope, {}).pop(key, None)

    def scope_items(self, scope: str) -> dict[str, Any]:
        """Return a copy of everything stored in ``scope``."""
        return dict(self._scopes.get(scope, {}))

    # -- Conversation buffer ---------------------------------------------
    def add_message(self, message: Message) -> None:
        """Append a message to the short-term conversation buffer."""
        self._messages.append(message)

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    def context_messages(self, system: str | None = None) -> list[Message]:
        """Return the recent messages that fit the token budget."""
        return self._window.trim(self._messages, system)

    async def compressed_context(self, system: str | None = None) -> list[Message]:
        """Return context with older overflow summarized (if a summarizer is set)."""
        return await self._window.compress(self._messages, system)

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of all scoped memory."""
        return {scope: dict(items) for scope, items in self._scopes.items()}

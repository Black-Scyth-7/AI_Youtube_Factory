"""Conversation memory management.

Manages the working context window: short-term memory (recent messages), context
trimming to a token budget, and a summarization interface for compressing older
turns. A long-term / vector memory backend plugs in behind
:class:`LongTermMemory` in a later phase.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.llm.messages import ChatRequest, Message, Role
from app.core.llm.tokenizer import heuristic_token_count


@runtime_checkable
class LongTermMemory(Protocol):
    """Interface for durable, retrievable memory (e.g. vector store)."""

    async def store(self, conversation_id: str, message: Message) -> None: ...

    async def recall(
        self, conversation_id: str, query: str, k: int = 5
    ) -> list[Message]: ...


@runtime_checkable
class Summarizer(Protocol):
    """Produces a concise summary of a set of messages."""

    async def summarize(self, messages: list[Message]) -> str: ...


def estimate_messages_tokens(messages: list[Message], system: str | None = None) -> int:
    """Estimate the token footprint of a message list."""
    request = ChatRequest(messages=messages, model="", system=system)
    return heuristic_token_count(request)


class WindowMemory:
    """Short-term memory that trims history to a token budget.

    Keeps the most recent messages that fit within ``max_tokens``; when a
    summarizer is provided, older messages are compressed into a single system
    summary message rather than dropped.
    """

    def __init__(
        self, max_tokens: int = 8000, summarizer: Summarizer | None = None
    ) -> None:
        self._max_tokens = max_tokens
        self._summarizer = summarizer

    def trim(self, messages: list[Message], system: str | None = None) -> list[Message]:
        """Return the tail of ``messages`` that fits within the token budget."""
        kept: list[Message] = []
        total = estimate_messages_tokens([], system)
        for message in reversed(messages):
            cost = estimate_messages_tokens([message])
            if total + cost > self._max_tokens and kept:
                break
            kept.append(message)
            total += cost
        kept.reverse()
        return kept

    async def compress(
        self, messages: list[Message], system: str | None = None
    ) -> list[Message]:
        """Summarize overflow messages into a single summary, keeping recent ones."""
        fitting = self.trim(messages, system)
        if len(fitting) == len(messages) or self._summarizer is None:
            return fitting
        overflow = messages[: len(messages) - len(fitting)]
        summary = await self._summarizer.summarize(overflow)
        summary_message = Message(
            role=Role.SYSTEM, content=f"Summary of earlier conversation:\n{summary}"
        )
        return [summary_message, *fitting]

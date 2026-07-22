"""Inter-agent communication.

A simple message bus with per-agent mailboxes for multi-agent collaboration.
Agents send directed or broadcast messages; a coordinator drains mailboxes to
route work. This is in-process now and can be backed by the durable event bus or
a broker later without changing call sites.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MessageType(StrEnum):
    """The intent of an agent message."""

    REQUEST = "request"
    RESPONSE = "response"
    DELEGATE = "delegate"
    BROADCAST = "broadcast"
    STATUS = "status"


@dataclass(slots=True)
class AgentMessage:
    """A message passed between agents."""

    sender: str
    recipient: str  # agent slug, or "*" for broadcast
    content: str
    type: MessageType = MessageType.REQUEST
    payload: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MessageBus:
    """Routes messages into per-recipient mailboxes."""

    def __init__(self) -> None:
        self._mailboxes: dict[str, deque[AgentMessage]] = defaultdict(deque)
        self._agents: set[str] = set()
        self.history: list[AgentMessage] = []

    def register(self, agent_slug: str) -> None:
        """Register an agent so it can receive broadcasts."""
        self._agents.add(agent_slug)
        self._mailboxes.setdefault(agent_slug, deque())

    def send(self, message: AgentMessage) -> None:
        """Deliver a message to its recipient(s)."""
        self.history.append(message)
        if message.recipient == "*":
            for slug in self._agents:
                if slug != message.sender:
                    self._mailboxes[slug].append(message)
        else:
            self._mailboxes[message.recipient].append(message)

    def receive(self, agent_slug: str) -> list[AgentMessage]:
        """Drain and return all pending messages for an agent."""
        mailbox = self._mailboxes.get(agent_slug)
        if not mailbox:
            return []
        drained = list(mailbox)
        mailbox.clear()
        return drained

    def pending(self, agent_slug: str) -> int:
        return len(self._mailboxes.get(agent_slug, deque()))

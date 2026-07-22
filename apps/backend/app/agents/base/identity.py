"""Agent identity.

The immutable identifying facts about an agent instance: who it is, what it is
for, and which capabilities/tags describe it. Kept separate from mutable runtime
state (see :mod:`app.agents.base.context`) and from persistence (the ``Agent``
ORM model).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class AgentIdentity:
    """The stable identity of an agent instance."""

    name: str
    slug: str
    description: str = ""
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    category: str = "general"
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def has_capability(self, capability: str) -> bool:
        """Return ``True`` if the agent advertises ``capability``."""
        return capability in self.capabilities

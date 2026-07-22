"""Agent registry.

A process-wide catalog of available agent *types*. Agents register a class plus
metadata (version, capabilities, tags, category, required permission) so the
manager and API can discover and instantiate them. Multiple versions of the same
slug can coexist; the highest registered version is the default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.base.agent import BaseAgent


@dataclass(slots=True)
class AgentRegistration:
    """A registered agent type with its discovery metadata."""

    slug: str
    version: str
    agent_cls: type[BaseAgent]
    name: str
    description: str
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    category: str = "general"
    required_permission: str = "agent.run"
    provider_independent: bool = True

    def create(self) -> BaseAgent:
        """Instantiate the registered agent."""
        return self.agent_cls()


def _version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return tuple(parts)


class AgentRegistry:
    """Holds agent registrations keyed by ``(slug, version)``."""

    def __init__(self) -> None:
        self._registry: dict[str, dict[str, AgentRegistration]] = {}

    def register(
        self,
        agent_cls: type[BaseAgent],
        *,
        required_permission: str = "agent.run",
    ) -> AgentRegistration:
        """Register an agent class from its identity."""
        identity = agent_cls.identity()
        registration = AgentRegistration(
            slug=identity.slug,
            version=identity.version,
            agent_cls=agent_cls,
            name=identity.name,
            description=identity.description,
            capabilities=identity.capabilities,
            tags=identity.tags,
            category=identity.category,
            required_permission=required_permission,
        )
        self._registry.setdefault(identity.slug, {})[identity.version] = registration
        return registration

    def get(self, slug: str, version: str | None = None) -> AgentRegistration:
        """Return a registration; the latest version if ``version`` is omitted."""
        versions = self._registry.get(slug)
        if not versions:
            raise KeyError(f"No agent registered for slug '{slug}'.")
        if version is not None:
            if version not in versions:
                raise KeyError(f"Agent '{slug}' has no version '{version}'.")
            return versions[version]
        latest = max(versions, key=_version_key)
        return versions[latest]

    def create(self, slug: str, version: str | None = None) -> BaseAgent:
        """Instantiate a registered agent."""
        return self.get(slug, version).create()

    def all(self) -> list[AgentRegistration]:
        """Return the latest registration for each slug."""
        return [self.get(slug) for slug in self._registry]

    def versions(self, slug: str) -> list[str]:
        return sorted(self._registry.get(slug, {}), key=_version_key)

    def discover(
        self,
        *,
        capability: str | None = None,
        tag: str | None = None,
        category: str | None = None,
    ) -> list[AgentRegistration]:
        """Find agents matching capability/tag/category filters."""
        results: list[AgentRegistration] = []
        for registration in self.all():
            if capability and capability not in registration.capabilities:
                continue
            if tag and tag not in registration.tags:
                continue
            if category and registration.category != category:
                continue
            results.append(registration)
        return results


_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Return the process agent-registry singleton (seeded with examples)."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        _seed_examples(_registry)
    return _registry


def set_agent_registry(registry: AgentRegistry) -> None:
    """Override the agent-registry singleton (used in tests)."""
    global _registry
    _registry = registry


def _seed_examples(registry: AgentRegistry) -> None:
    """Register the built-in example agents."""
    from app.agents.examples.assistant_agent import AssistantAgent
    from app.agents.examples.echo_agent import EchoAgent
    from app.agents.examples.research_agent import ResearchAgent

    registry.register(EchoAgent)
    registry.register(AssistantAgent)
    registry.register(ResearchAgent)

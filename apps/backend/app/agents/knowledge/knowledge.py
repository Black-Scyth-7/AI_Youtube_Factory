"""Agent knowledge base.

Knowledge is separate from memory: it is the relatively stable body of facts,
policies, documentation, templates, and preferences an agent can consult.
Entries are tagged and keyword-searchable. RAG / vector retrieval plugs in behind
the same ``search`` surface in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class KnowledgeKind(StrEnum):
    """Category of a knowledge entry."""

    POLICY = "policy"
    DOCUMENTATION = "documentation"
    TEMPLATE = "template"
    FACT = "fact"
    PREFERENCE = "preference"
    RULE = "rule"


@dataclass(slots=True)
class KnowledgeEntry:
    """A single piece of knowledge."""

    title: str
    content: str
    kind: KnowledgeKind = KnowledgeKind.FACT
    tags: tuple[str, ...] = ()

    def matches(self, query: str) -> int:
        """Return a simple relevance score for ``query`` (0 = no match)."""
        q = query.lower()
        score = 0
        haystack = f"{self.title} {self.content} {' '.join(self.tags)}".lower()
        for term in q.split():
            score += haystack.count(term)
        return score


class KnowledgeBase:
    """An in-memory, keyword-searchable knowledge store."""

    def __init__(self, entries: list[KnowledgeEntry] | None = None) -> None:
        self._entries: list[KnowledgeEntry] = list(entries or [])

    def add(self, entry: KnowledgeEntry) -> None:
        self._entries.append(entry)

    def all(self) -> list[KnowledgeEntry]:
        return list(self._entries)

    def by_kind(self, kind: KnowledgeKind) -> list[KnowledgeEntry]:
        return [e for e in self._entries if e.kind == kind]

    def search(self, query: str, *, limit: int = 5) -> list[str]:
        """Return the contents of the top ``limit`` entries matching ``query``."""
        scored = [(e.matches(query), e) for e in self._entries]
        ranked = sorted(
            (pair for pair in scored if pair[0] > 0),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [entry.content for _, entry in ranked[:limit]]

    def policies(self) -> list[str]:
        """Return the contents of all policy/rule entries."""
        return [
            e.content
            for e in self._entries
            if e.kind in (KnowledgeKind.POLICY, KnowledgeKind.RULE)
        ]


@dataclass(slots=True)
class KnowledgeContext:
    """A snapshot of knowledge relevant to a task, injected into prompts."""

    facts: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render the knowledge context as a prompt-ready block."""
        parts: list[str] = []
        if self.policies:
            parts.append("Policies:\n" + "\n".join(f"- {p}" for p in self.policies))
        if self.facts:
            parts.append(
                "Relevant knowledge:\n" + "\n".join(f"- {f}" for f in self.facts)
            )
        return "\n\n".join(parts)

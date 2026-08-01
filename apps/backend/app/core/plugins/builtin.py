"""Plugins that ship with the platform.

Deliberately small and useful rather than demonstrative: each one does
something a user would otherwise do by hand, and together they exercise the
parts of the system a third-party plugin will use — reading context, returning
a patch, and declining to act.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.plugins.manifest import Capability, HookName, PluginManifest
from app.core.plugins.registry import HookContext, register_plugin

# -- Title case -------------------------------------------------------------
#: Words left lowercase unless they start or end the title.
_MINOR_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "in",
        "nor",
        "of",
        "on",
        "or",
        "the",
        "to",
        "up",
        "via",
        "vs",
    ]
)

TITLE_CASE = PluginManifest(
    name="title-case",
    version="1.0.0",
    display_name="Title case",
    description="Applies headline capitalisation to video titles.",
    author="AI YouTube Factory",
    hooks=[HookName.VIDEO_CREATED],
    capabilities=[Capability.READ_CONTEXT, Capability.WRITE_CONTEXT],
    priority=10,
)


def headline_case(title: str) -> str:
    """Capitalise a title, leaving minor words lowercase inside it."""
    words = title.split()
    out: list[str] = []
    for index, word in enumerate(words):
        lowered = word.lower()
        first_or_last = index == 0 or index == len(words) - 1
        if lowered in _MINOR_WORDS and not first_or_last:
            out.append(lowered)
        elif word.isupper() and len(word) > 1:
            # Leave acronyms alone: "AI" must not become "Ai".
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


async def _title_case(context: HookContext) -> dict[str, Any] | None:
    title = context.payload.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    formatted = headline_case(title)
    # Returning nothing when nothing changed keeps the result list honest
    # about which plugins actually did something.
    return {"title": formatted} if formatted != title else None


# -- Hashtag extraction ------------------------------------------------------
HASHTAGS = PluginManifest(
    name="hashtag-extract",
    version="1.0.0",
    display_name="Hashtag extraction",
    description="Collects #hashtags from the description into a tag list.",
    author="AI YouTube Factory",
    hooks=[HookName.BEFORE_PUBLISH],
    capabilities=[Capability.READ_CONTEXT, Capability.WRITE_CONTEXT],
    priority=20,
)

_HASHTAG_RE = re.compile(r"#([A-Za-z][A-Za-z0-9_]{1,49})")
#: YouTube ignores hashtags past the first few and flags stuffing.
_MAX_TAGS = 15


async def _extract_hashtags(context: HookContext) -> dict[str, Any] | None:
    description = context.payload.get("description")
    if not isinstance(description, str):
        return None

    seen: list[str] = []
    for match in _HASHTAG_RE.finditer(description):
        tag = match.group(1).lower()
        if tag not in seen:
            seen.append(tag)
    if not seen:
        return None

    existing = context.payload.get("tags")
    tags = list(existing) if isinstance(existing, list) else []
    for tag in seen:
        if tag not in tags:
            tags.append(tag)
    return {"tags": tags[:_MAX_TAGS]}


# -- Description length guard -----------------------------------------------
DESCRIPTION_GUARD = PluginManifest(
    name="description-guard",
    version="1.0.0",
    display_name="Description guard",
    description="Truncates descriptions to YouTube's limit on a word boundary.",
    author="AI YouTube Factory",
    hooks=[HookName.BEFORE_PUBLISH],
    capabilities=[Capability.READ_CONTEXT, Capability.WRITE_CONTEXT],
    # After hashtag extraction, so tags are read from the full text rather
    # than from whatever survived truncation.
    priority=30,
)

#: YouTube rejects descriptions longer than this.
_MAX_DESCRIPTION = 5000


async def _guard_description(context: HookContext) -> dict[str, Any] | None:
    description = context.payload.get("description")
    if not isinstance(description, str) or len(description) <= _MAX_DESCRIPTION:
        return None

    cut = description[:_MAX_DESCRIPTION]
    boundary = cut.rfind(" ")
    # Only back up to a word boundary if one is reasonably near the end;
    # otherwise a description with no spaces would be truncated to nothing.
    if boundary > _MAX_DESCRIPTION - 200:
        cut = cut[:boundary]
    return {"description": cut.rstrip() + "…"}


def register_builtin_plugins() -> None:
    """Register the built-in plugins. Idempotent."""
    from app.core.plugins.registry import REGISTRY

    for manifest, handler in (
        (TITLE_CASE, _title_case),
        (HASHTAGS, _extract_hashtags),
        (DESCRIPTION_GUARD, _guard_description),
    ):
        if REGISTRY.get(manifest.name) is None:
            register_plugin(manifest, {manifest.hooks[0]: handler})

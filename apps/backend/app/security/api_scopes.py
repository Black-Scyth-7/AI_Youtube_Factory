"""Scopes for API keys.

Separate from the RBAC permissions a *user* holds. A key is issued by a user and
can never do more than that user could, but it is usually meant to do far less:
a key on a build server should read videos, not delete an organization. The two
are checked together — the key's scopes narrow the user's permissions, never
widen them.

Scopes are ``resource:action``, and a ``:write`` scope does not imply
``:read``. Implication rules are the kind of thing that seems convenient until
someone grants ``video:write`` to a webhook and discovers it can enumerate the
catalogue too.
"""

from __future__ import annotations

from typing import Final

#: Every scope that may be granted, with what it allows.
API_SCOPES: Final[dict[str, str]] = {
    "video:read": "List and read videos and their versions",
    "video:write": "Create and update videos",
    "channel:read": "List and read connected channels",
    "project:read": "List and read projects and workspaces",
    "pipeline:read": "Read pipeline runs and their artifacts",
    "pipeline:write": "Start and advance pipeline runs",
    "analytics:read": "Read published-video analytics",
    "usage:read": "Read the organization's usage and quotas",
}

ALL_SCOPES: Final[frozenset[str]] = frozenset(API_SCOPES)

#: A sensible default for a key created without an explicit list: read-only.
#: Defaulting to write access is how a key meant for a dashboard ends up able
#: to publish.
DEFAULT_SCOPES: Final[tuple[str, ...]] = (
    "video:read",
    "channel:read",
    "project:read",
    "pipeline:read",
    "analytics:read",
)

#: The RBAC permission a caller must also hold for each scope. A key cannot
#: grant its owner something the owner does not have.
SCOPE_REQUIRES_PERMISSION: Final[dict[str, str]] = {
    "video:write": "video.create",
    "pipeline:write": "video.create",
    "analytics:read": "analytics.read",
    "usage:read": "billing.read",
}


def validate_scopes(scopes: list[str]) -> list[str]:
    """Return ``scopes`` unchanged, or raise if any is unknown.

    Silently dropping an unrecognised scope would issue a key that appears to
    have access it does not, and the failure would surface much later as a
    confusing 403.
    """
    unknown = sorted(set(scopes) - ALL_SCOPES)
    if unknown:
        raise ValueError(
            f"Unknown API scopes: {', '.join(unknown)}. "
            f"Valid scopes: {', '.join(sorted(ALL_SCOPES))}"
        )
    return scopes

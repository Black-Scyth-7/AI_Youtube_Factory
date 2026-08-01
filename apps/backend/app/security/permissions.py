"""Permission catalog and default role → permission mappings.

The catalog is the single source of truth for every granular permission in the
platform. System roles are seeded from ``DEFAULT_ROLE_PERMISSIONS`` on startup
and for each new organization.
"""

from __future__ import annotations

from app.models.enums import SystemRole

# ---- Granular permission slugs ------------------------------------------
PERMISSIONS: dict[str, str] = {
    "organization.manage": "Manage organization settings",
    "organization.delete": "Delete the organization",
    "member.manage": "Invite, remove, and change member roles",
    "team.manage": "Create and manage teams",
    "role.manage": "Create and manage custom roles",
    "billing.read": "View plans, invoices, and usage",
    "billing.manage": "Manage billing and subscriptions",
    "project.create": "Create projects",
    "project.delete": "Delete projects",
    "channel.manage": "Connect and manage YouTube channels",
    "video.create": "Create videos",
    "video.delete": "Delete videos",
    "video.publish": "Publish videos",
    "prompt.edit": "Edit prompts",
    "agent.run": "Run AI agents",
    "agent.manage": "Create, configure, and manage AI agents",
    "analytics.read": "Read analytics",
    "api_key.manage": "Create and revoke API keys",
    "audit.read": "Read audit logs",
}

ALL_PERMISSIONS: frozenset[str] = frozenset(PERMISSIONS)

_MANAGER_PERMISSIONS = frozenset(
    {
        "team.manage",
        "project.create",
        "project.delete",
        "channel.manage",
        "video.create",
        "video.delete",
        "video.publish",
        "prompt.edit",
        "agent.run",
        "agent.manage",
        "analytics.read",
        # Seeing the bill is not the same as being able to change the plan; a
        # manager spending the quota needs to know how much is left.
        "billing.read",
    }
)

_EDITOR_PERMISSIONS = frozenset(
    {
        "video.create",
        "video.publish",
        "prompt.edit",
        "agent.run",
        "analytics.read",
    }
)

_VIEWER_PERMISSIONS = frozenset({"analytics.read"})

# ---- Default role → permission sets -------------------------------------
DEFAULT_ROLE_PERMISSIONS: dict[SystemRole, frozenset[str]] = {
    SystemRole.OWNER: ALL_PERMISSIONS,
    SystemRole.ADMIN: ALL_PERMISSIONS - {"organization.delete", "billing.manage"},
    SystemRole.MANAGER: _MANAGER_PERMISSIONS,
    SystemRole.EDITOR: _EDITOR_PERMISSIONS,
    SystemRole.VIEWER: _VIEWER_PERMISSIONS,
}

ROLE_DISPLAY: dict[SystemRole, str] = {
    SystemRole.OWNER: "Owner",
    SystemRole.ADMIN: "Admin",
    SystemRole.MANAGER: "Manager",
    SystemRole.EDITOR: "Editor",
    SystemRole.VIEWER: "Viewer",
}

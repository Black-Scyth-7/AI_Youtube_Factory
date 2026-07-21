"""Enumerations used by identity models (stored as strings)."""

from __future__ import annotations

from enum import StrEnum


class SystemRole(StrEnum):
    """Built-in role slugs seeded for every organization."""

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    EDITOR = "editor"
    VIEWER = "viewer"


class MemberStatus(StrEnum):
    """Membership lifecycle within an organization or team."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class InvitationStatus(StrEnum):
    """Invitation lifecycle."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OAuthProvider(StrEnum):
    """Supported external identity providers."""

    GOOGLE = "google"
    GITHUB = "github"


class AuditAction(StrEnum):
    """Auditable actions recorded in the audit log."""

    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_LOGOUT = "user.logout"
    EMAIL_VERIFIED = "user.email_verified"
    PASSWORD_CHANGED = "user.password_changed"
    PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    PASSWORD_RESET = "user.password_reset"
    OAUTH_LOGIN = "user.oauth_login"
    SESSION_REVOKED = "session.revoked"
    SESSIONS_REVOKED_ALL = "session.revoked_all"
    ORG_CREATED = "organization.created"
    ORG_UPDATED = "organization.updated"
    MEMBER_ROLE_UPDATED = "organization.member_role_updated"
    MEMBER_REMOVED = "organization.member_removed"
    TEAM_CREATED = "team.created"
    INVITE_SENT = "invitation.sent"
    INVITE_ACCEPTED = "invitation.accepted"
    INVITE_REVOKED = "invitation.revoked"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_USED = "api_key.used"

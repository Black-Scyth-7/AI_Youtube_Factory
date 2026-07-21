"""Repository layer — async data access, one class per aggregate."""

from app.repositories.api_key import ApiKeyRepository
from app.repositories.auth import (
    EmailVerificationTokenRepository,
    OAuthAccountRepository,
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    SessionRepository,
)
from app.repositories.base import BaseRepository
from app.repositories.invitation import AuditLogRepository, InvitationRepository
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.repositories.rbac import PermissionRepository, RoleRepository
from app.repositories.team import TeamMemberRepository, TeamRepository
from app.repositories.user import ProfileRepository, UserRepository

__all__ = [
    "ApiKeyRepository",
    "AuditLogRepository",
    "BaseRepository",
    "EmailVerificationTokenRepository",
    "InvitationRepository",
    "OAuthAccountRepository",
    "OrganizationMemberRepository",
    "OrganizationRepository",
    "PasswordResetTokenRepository",
    "PermissionRepository",
    "ProfileRepository",
    "RefreshTokenRepository",
    "RoleRepository",
    "SessionRepository",
    "TeamMemberRepository",
    "TeamRepository",
    "UserRepository",
]

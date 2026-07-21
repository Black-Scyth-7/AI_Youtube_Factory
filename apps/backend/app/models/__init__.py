"""ORM model package.

Importing every model module here registers it on ``Base.metadata`` so Alembic
autogenerate and metadata-create see the full schema.
"""

from app.models.api_key import ApiKey
from app.models.audit import AuditLog
from app.models.auth import (
    EmailVerificationToken,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    Session,
)
from app.models.base import Base
from app.models.enums import (
    AuditAction,
    InvitationStatus,
    MemberStatus,
    OAuthProvider,
    SystemRole,
)
from app.models.invitation import Invitation
from app.models.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Permission, Role, role_permissions
from app.models.team import Team, TeamMember
from app.models.types import GUID
from app.models.user import Profile, User

__all__ = [
    "GUID",
    "ApiKey",
    "AuditAction",
    "AuditLog",
    "AuditMixin",
    "Base",
    "EmailVerificationToken",
    "Invitation",
    "InvitationStatus",
    "MemberStatus",
    "OAuthAccount",
    "OAuthProvider",
    "Organization",
    "OrganizationMember",
    "PasswordResetToken",
    "Permission",
    "Profile",
    "RefreshToken",
    "Role",
    "Session",
    "SoftDeleteMixin",
    "SystemRole",
    "Team",
    "TeamMember",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "role_permissions",
]

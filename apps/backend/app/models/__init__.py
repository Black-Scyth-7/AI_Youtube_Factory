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
from app.models.domain_enums import (
    FeatureFlagScope,
    MediaStatus,
    ProjectStatus,
    VideoStatus,
    WorkflowExecutionStatus,
)
from app.models.enums import (
    AuditAction,
    InvitationStatus,
    MemberStatus,
    OAuthProvider,
    SystemRole,
)
from app.models.infra import ActivityLog, FeatureFlag
from app.models.invitation import Invitation
from app.models.llm import (
    Conversation,
    ConversationMessage,
    ConversationSummary,
    LLMCostRollup,
    LLMRequest,
    LLMUsageRollup,
    ModelConfiguration,
    PromptTemplate,
    PromptVersion,
    ProviderConfiguration,
    ToolExecution,
)
from app.models.media import Folder, MediaFile, Tag, video_tags
from app.models.mixins import (
    ActorMixin,
    AuditMixin,
    EntityMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionMixin,
)
from app.models.organization import Organization, OrganizationMember
from app.models.rbac import Permission, Role, role_permissions
from app.models.team import Team, TeamMember
from app.models.types import GUID
from app.models.user import Profile, User
from app.models.video import Video, VideoVersion
from app.models.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowNode,
)
from app.models.workspace import Channel, Project, Workspace

__all__ = [
    "GUID",
    "ActivityLog",
    "ActorMixin",
    "ApiKey",
    "AuditAction",
    "AuditLog",
    "AuditMixin",
    "Base",
    "Channel",
    "Conversation",
    "ConversationMessage",
    "ConversationSummary",
    "EmailVerificationToken",
    "EntityMixin",
    "FeatureFlag",
    "FeatureFlagScope",
    "Folder",
    "Invitation",
    "InvitationStatus",
    "LLMCostRollup",
    "LLMRequest",
    "LLMUsageRollup",
    "MediaFile",
    "MediaStatus",
    "MemberStatus",
    "ModelConfiguration",
    "OAuthAccount",
    "OAuthProvider",
    "Organization",
    "OrganizationMember",
    "PasswordResetToken",
    "Permission",
    "Profile",
    "Project",
    "ProjectStatus",
    "PromptTemplate",
    "PromptVersion",
    "ProviderConfiguration",
    "RefreshToken",
    "Role",
    "Session",
    "SoftDeleteMixin",
    "SystemRole",
    "Tag",
    "Team",
    "TeamMember",
    "TimestampMixin",
    "ToolExecution",
    "UUIDPrimaryKeyMixin",
    "User",
    "VersionMixin",
    "Video",
    "VideoStatus",
    "VideoVersion",
    "Workflow",
    "WorkflowEdge",
    "WorkflowExecution",
    "WorkflowExecutionStatus",
    "WorkflowNode",
    "Workspace",
    "role_permissions",
    "video_tags",
]

"""Enumerations for Phase 03 domain models (stored as strings)."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class VideoStatus(StrEnum):
    DRAFT = "draft"
    RESEARCHING = "researching"
    SCRIPTING = "scripting"
    RENDERING = "rendering"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"


class MediaStatus(StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    PROCESSING = "processing"
    FAILED = "failed"


class WorkflowExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"


class NodeRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    #: Excluded because no incoming edge condition was satisfied.
    SKIPPED = "skipped"


class NodeKind(StrEnum):
    """Built-in node behaviours the engine understands directly."""

    TASK = "task"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    MERGE = "merge"


class FeatureFlagScope(StrEnum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    USER = "user"


# -- Billing ------------------------------------------------------------------
class BillingInterval(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


# -- Notifications ------------------------------------------------------------
class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"


class WebhookDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXHAUSTED = "exhausted"


# -- Jobs ---------------------------------------------------------------------
class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderJobKind(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    THUMBNAIL = "thumbnail"
    SUBTITLES = "subtitles"


# -- Usage --------------------------------------------------------------------
class UsageMetric(StrEnum):
    """Billable units. LLM tokens are tracked separately in ``llm_request``."""

    VIDEO_RENDER = "video_render"
    STORAGE_GB_HOURS = "storage_gb_hours"
    PUBLISH = "publish"
    AGENT_RUN = "agent_run"
    API_CALL = "api_call"


# -- Video pipeline -----------------------------------------------------------
class PipelineStage(StrEnum):
    RESEARCH = "research"
    SCRIPT = "script"
    VOICEOVER = "voiceover"
    RENDER = "render"
    PUBLISH = "publish"
    ANALYTICS = "analytics"
    LEARNING = "learning"
    DONE = "done"
    FAILED = "failed"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"

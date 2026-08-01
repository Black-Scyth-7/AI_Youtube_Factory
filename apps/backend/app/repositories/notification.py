"""Repositories for notifications and webhooks."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.models.domain_enums import NotificationStatus, WebhookDeliveryStatus
from app.models.notification import (
    Notification,
    NotificationPreference,
    Webhook,
    WebhookDelivery,
)
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        stmt = self._base_query().where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(
            self._base_query()
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .subquery()
        )
        return int((await self.session.execute(stmt)).scalar_one())


class NotificationPreferenceRepository(BaseRepository[NotificationPreference]):
    model = NotificationPreference

    async def get_for(
        self, user_id: uuid.UUID, category: str, channel: str
    ) -> NotificationPreference | None:
        return await self.find_by(user_id=user_id, category=category, channel=channel)


class WebhookRepository(BaseRepository[Webhook]):
    model = Webhook

    async def list_all_for_organization(
        self, organization_id: uuid.UUID
    ) -> list[Webhook]:
        stmt = (
            self._base_query()
            .where(Webhook.organization_id == organization_id)
            .order_by(Webhook.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_active_for_event(
        self, organization_id: uuid.UUID, event_type: str
    ) -> list[Webhook]:
        """Active webhooks for an organization that subscribe to ``event_type``.

        The event list is JSON, so subscription is filtered in Python rather
        than with a dialect-specific JSON containment operator.
        """
        stmt = self._base_query().where(
            Webhook.organization_id == organization_id,
            Webhook.is_active.is_(True),
        )
        hooks = (await self.session.execute(stmt)).scalars().all()
        return [h for h in hooks if event_type in h.events or "*" in h.events]


class WebhookDeliveryRepository(BaseRepository[WebhookDelivery]):
    model = WebhookDelivery

    async def list_due_retries(
        self, now: datetime, limit: int = 100
    ) -> list[WebhookDelivery]:
        stmt = (
            self._base_query()
            .where(
                WebhookDelivery.status == WebhookDeliveryStatus.FAILED.value,
                WebhookDelivery.next_retry_at.is_not(None),
                WebhookDelivery.next_retry_at <= now,
            )
            .order_by(WebhookDelivery.next_retry_at)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_webhook(
        self, webhook_id: uuid.UUID, limit: int = 50
    ) -> list[WebhookDelivery]:
        stmt = (
            self._base_query()
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


__all__ = [
    "NotificationPreferenceRepository",
    "NotificationRepository",
    "NotificationStatus",
    "WebhookDeliveryRepository",
    "WebhookRepository",
]

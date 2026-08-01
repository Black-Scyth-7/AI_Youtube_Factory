"""Notification and webhook services.

Webhook secrets follow the API-key pattern: the raw value is returned once and
only its hash is stored. Delivery retries use exponential backoff and give up
after a bounded number of attempts rather than retrying a dead endpoint forever.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import NotFoundError, ValidationError
from app.models.domain_enums import (
    NotificationChannel,
    NotificationStatus,
    WebhookDeliveryStatus,
)
from app.models.notification import (
    Notification,
    NotificationPreference,
    Webhook,
    WebhookDelivery,
)
from app.repositories.notification import (
    NotificationPreferenceRepository,
    NotificationRepository,
    WebhookDeliveryRepository,
    WebhookRepository,
)
from app.security.tokens import generate_token, hash_token

#: Backoff schedule in seconds; the length also caps the number of attempts.
RETRY_BACKOFF_SECONDS = (60, 300, 1800, 7200)
MAX_RESPONSE_BODY = 2048


class NotificationService:
    """Creates and reads user notifications, honouring preferences."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)
        self.preferences = NotificationPreferenceRepository(session)

    async def notify(
        self,
        user_id: uuid.UUID,
        category: str,
        title: str,
        *,
        body: str | None = None,
        channel: str = NotificationChannel.IN_APP.value,
        organization_id: uuid.UUID | None = None,
        action_url: str | None = None,
    ) -> Notification | None:
        """Create a notification, or return ``None`` if the user opted out."""
        preference = await self.preferences.get_for(user_id, category, channel)
        if preference is not None and not preference.enabled:
            return None

        notification = Notification(
            user_id=user_id,
            organization_id=organization_id,
            category=category,
            channel=channel,
            title=title,
            body=body,
            action_url=action_url,
            status=NotificationStatus.PENDING.value,
        )
        return await self.repo.add(notification)

    async def mark_read(self, notification_id: uuid.UUID) -> Notification:
        notification = await self.repo.get(notification_id)
        if notification is None:
            raise NotFoundError("Notification not found.")
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            notification.status = NotificationStatus.READ.value
            await self.session.flush()
        return notification

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        unread = await self.repo.list_for_user(user_id, unread_only=True, limit=1000)
        now = datetime.now(UTC)
        for notification in unread:
            notification.read_at = now
            notification.status = NotificationStatus.READ.value
        await self.session.flush()
        return len(unread)

    async def list_for_user(
        self, user_id: uuid.UUID, *, unread_only: bool = False
    ) -> list[Notification]:
        return await self.repo.list_for_user(user_id, unread_only=unread_only)

    async def unread_count(self, user_id: uuid.UUID) -> int:
        return await self.repo.count_unread(user_id)

    async def set_preference(
        self, user_id: uuid.UUID, category: str, channel: str, *, enabled: bool
    ) -> NotificationPreference:
        preference = await self.preferences.get_for(user_id, category, channel)
        if preference is None:
            preference = NotificationPreference(
                user_id=user_id, category=category, channel=channel, enabled=enabled
            )
            return await self.preferences.add(preference)
        preference.enabled = enabled
        await self.session.flush()
        return preference


def sign_payload(secret: str, payload: str) -> str:
    """Return the hex HMAC-SHA256 signature a receiver should verify."""
    return hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class WebhookService:
    """Manages webhook subscriptions and their delivery attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WebhookRepository(session)
        self.deliveries = WebhookDeliveryRepository(session)

    async def create(
        self,
        organization_id: uuid.UUID,
        name: str,
        url: str,
        events: list[str],
    ) -> tuple[Webhook, str]:
        """Create a webhook, returning it with its secret shown exactly once."""
        if not url.startswith(("http://", "https://")):
            raise ValidationError("Webhook URL must be http or https.")
        if not events:
            raise ValidationError("Subscribe to at least one event.")

        secret = generate_token()
        webhook = Webhook(
            organization_id=organization_id,
            name=name,
            url=url,
            events=events,
            secret_hash=hash_token(secret),
        )
        await self.repo.add(webhook)
        return webhook, secret

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Webhook]:
        return await self.repo.list_all_for_organization(organization_id)

    async def enqueue_event(
        self, organization_id: uuid.UUID, event_type: str, payload: dict[str, object]
    ) -> list[WebhookDelivery]:
        """Queue a delivery for every webhook subscribed to ``event_type``."""
        hooks = await self.repo.list_active_for_event(organization_id, event_type)
        created: list[WebhookDelivery] = []
        for hook in hooks:
            delivery = WebhookDelivery(
                webhook_id=hook.id,
                event_type=event_type,
                status=WebhookDeliveryStatus.PENDING.value,
                payload=dict(payload),
            )
            created.append(await self.deliveries.add(delivery))
        return created

    async def record_success(
        self, delivery_id: uuid.UUID, response_status: int, body: str = ""
    ) -> WebhookDelivery:
        delivery = await self.deliveries.get(delivery_id)
        if delivery is None:
            raise NotFoundError("Webhook delivery not found.")

        delivery.attempt += 1
        delivery.status = WebhookDeliveryStatus.DELIVERED.value
        delivery.response_status = response_status
        delivery.response_body = body[:MAX_RESPONSE_BODY]
        delivery.delivered_at = datetime.now(UTC)
        delivery.next_retry_at = None

        webhook = await self.repo.get(delivery.webhook_id)
        if webhook is not None:
            webhook.failure_count = 0
            webhook.last_success_at = delivery.delivered_at
        await self.session.flush()
        return delivery

    async def record_failure(
        self,
        delivery_id: uuid.UUID,
        *,
        error: str,
        response_status: int | None = None,
    ) -> WebhookDelivery:
        """Record a failed attempt and schedule the next, or give up."""
        delivery = await self.deliveries.get(delivery_id)
        if delivery is None:
            raise NotFoundError("Webhook delivery not found.")

        delivery.attempt += 1
        delivery.response_status = response_status
        delivery.error = error[:512]

        if delivery.attempt >= len(RETRY_BACKOFF_SECONDS):
            delivery.status = WebhookDeliveryStatus.EXHAUSTED.value
            delivery.next_retry_at = None
        else:
            delivery.status = WebhookDeliveryStatus.FAILED.value
            delay = RETRY_BACKOFF_SECONDS[delivery.attempt]
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        webhook = await self.repo.get(delivery.webhook_id)
        if webhook is not None:
            webhook.failure_count += 1
            webhook.last_failure_at = datetime.now(UTC)
        await self.session.flush()
        return delivery

    async def due_retries(self, limit: int = 100) -> list[WebhookDelivery]:
        return await self.deliveries.list_due_retries(datetime.now(UTC), limit=limit)

    @staticmethod
    def signature_for(secret: str, payload: dict[str, object]) -> str:
        """Signature for a payload, serialised the way delivery will send it."""
        return sign_payload(secret, json.dumps(payload, sort_keys=True))

"""High-level transactional email service.

Renders and dispatches the platform's transactional emails (verification, reset,
invitation) through the configured :class:`EmailProvider`.
"""

from __future__ import annotations

from app.config import settings
from app.services.email.base import EmailMessage, EmailProvider
from app.services.email.smtp import ConsoleEmailProvider, SMTPEmailProvider
from app.services.email.templates import render


def get_email_provider() -> EmailProvider:
    """Return the configured email provider (console when email is disabled)."""
    return SMTPEmailProvider() if settings.email_enabled else ConsoleEmailProvider()


class EmailService:
    """Sends transactional emails."""

    def __init__(self, provider: EmailProvider | None = None) -> None:
        self._provider = provider or get_email_provider()

    async def send_verification(self, *, to: str, token: str) -> None:
        url = f"{settings.frontend_url}/verify-email?token={token}"
        html, text = render(
            heading="Verify your email",
            intro=(
                "Welcome to AI YouTube Factory. Confirm your email to activate "
                "your account."
            ),
            cta="Verify email",
            url=url,
            footer=(
                f"This link expires in {settings.email_verification_expire_hours} "
                "hours."
            ),
        )
        await self._provider.send(
            EmailMessage(
                to=to, subject="Verify your email", html_body=html, text_body=text
            )
        )

    async def send_password_reset(self, *, to: str, token: str) -> None:
        url = f"{settings.frontend_url}/reset-password?token={token}"
        html, text = render(
            heading="Reset your password",
            intro=(
                "We received a request to reset your password. If this wasn't "
                "you, ignore this email."
            ),
            cta="Reset password",
            url=url,
            footer=f"This link expires in {settings.password_reset_expire_hours} hours.",
        )
        await self._provider.send(
            EmailMessage(
                to=to, subject="Reset your password", html_body=html, text_body=text
            )
        )

    async def send_invitation(self, *, to: str, token: str, org_name: str) -> None:
        url = f"{settings.frontend_url}/invitations/accept?token={token}"
        html, text = render(
            heading=f"You're invited to {org_name}",
            intro=f"You have been invited to join {org_name} on AI YouTube Factory.",
            cta="Accept invitation",
            url=url,
            footer=f"This invitation expires in {settings.invitation_expire_days} days.",
        )
        await self._provider.send(
            EmailMessage(
                to=to,
                subject=f"Invitation to join {org_name}",
                html_body=html,
                text_body=text,
            )
        )

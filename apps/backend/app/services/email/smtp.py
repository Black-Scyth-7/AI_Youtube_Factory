"""SMTP email provider."""

from __future__ import annotations

from email.message import EmailMessage as MIMEMessage

import aiosmtplib

from app.config import settings
from app.logging import get_logger
from app.services.email.base import EmailMessage, EmailProvider

logger = get_logger(__name__)


class SMTPEmailProvider(EmailProvider):
    """Sends email via SMTP using ``aiosmtplib``."""

    async def send(self, message: EmailMessage) -> None:
        mime = MIMEMessage()
        mime["From"] = f"{settings.email_from_name} <{settings.email_from}>"
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")

        await aiosmtplib.send(
            mime,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
        logger.info("email.sent", extra={"to": message.to, "subject": message.subject})


class ConsoleEmailProvider(EmailProvider):
    """Development provider that logs emails instead of sending them."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email.console",
            extra={
                "to": message.to,
                "subject": message.subject,
                "body_preview": message.text_body[:2000],
            },
        )

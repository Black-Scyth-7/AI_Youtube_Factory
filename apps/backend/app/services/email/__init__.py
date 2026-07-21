"""Email provider abstraction and transactional email service."""

from app.services.email.base import EmailMessage, EmailProvider
from app.services.email.service import EmailService, get_email_provider

__all__ = ["EmailMessage", "EmailProvider", "EmailService", "get_email_provider"]

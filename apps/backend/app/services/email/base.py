"""Email provider abstraction — interfaces.

Application code sends email through :class:`EmailProvider`. Concrete providers
(SMTP now; Resend/SendGrid/SES/Mailgun later) live behind this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class EmailMessage:
    """A rendered email ready to send."""

    to: str
    subject: str
    html_body: str
    text_body: str


@runtime_checkable
class EmailProvider(Protocol):
    """The contract all email providers implement."""

    async def send(self, message: EmailMessage) -> None:
        """Deliver ``message``."""
        ...

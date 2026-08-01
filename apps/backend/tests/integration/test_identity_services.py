"""Service-level tests for identity flows that need captured email tokens."""

from __future__ import annotations

import re

import pytest
from app.exceptions.base import ForbiddenError, UnauthorizedError, ValidationError
from app.models.enums import OAuthProvider, SystemRole
from app.services.api_key import ApiKeyService
from app.services.auth import AuthService
from app.services.email import EmailService
from app.services.email.base import EmailMessage, EmailProvider
from app.services.invitation import InvitationService
from app.services.oauth import OAuthProfile
from app.services.organization import OrganizationService
from app.services.rbac import RBACService
from app.services.token_service import RequestContext
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_PASSWORD = "Str0ng!Passw0rd"
_NEW_PASSWORD = "N3w!Passw0rd$"
_CTX = RequestContext(ip_address="127.0.0.1")


class CapturingEmailProvider(EmailProvider):
    """Records sent emails so tests can extract one-time tokens."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def last_token(self) -> str:
        match = re.search(r"token=([^\s]+)", self.messages[-1].text_body)
        assert match, "no token found in email body"
        return match.group(1)


def _auth_with_capture(
    session: AsyncSession,
) -> tuple[AuthService, CapturingEmailProvider]:
    cap = CapturingEmailProvider()
    return AuthService(session, email_service=EmailService(provider=cap)), cap


async def test_email_verification_flow(session: AsyncSession) -> None:
    auth, cap = _auth_with_capture(session)
    user = await auth.register(
        email="v@example.com", username="veri", password=_PASSWORD, display_name=None
    )
    assert user.is_verified is False
    token = cap.last_token()
    await auth.verify_email(token)
    assert user.is_verified is True

    # Token is single-use.
    with pytest.raises(ValidationError):
        await auth.verify_email(token)


async def test_password_reset_flow(session: AsyncSession) -> None:
    auth, cap = _auth_with_capture(session)
    await auth.register(
        email="r@example.com", username="reset", password=_PASSWORD, display_name=None
    )
    await auth.forgot_password("r@example.com")
    token = cap.last_token()
    await auth.reset_password(token=token, new_password=_NEW_PASSWORD)

    # New password works; old one does not.
    issued = await auth.login(email="r@example.com", password=_NEW_PASSWORD, ctx=_CTX)
    assert issued.access_token
    with pytest.raises(UnauthorizedError):
        await auth.login(email="r@example.com", password=_PASSWORD, ctx=_CTX)


async def test_forgot_password_unknown_email_is_silent(session: AsyncSession) -> None:
    auth, cap = _auth_with_capture(session)
    await auth.forgot_password("ghost@example.com")
    assert cap.messages == []  # no email sent, no error raised


async def test_oauth_login_creates_and_links(session: AsyncSession) -> None:
    auth = AuthService(
        session, email_service=EmailService(provider=CapturingEmailProvider())
    )
    profile = OAuthProfile(
        provider=OAuthProvider.GITHUB,
        account_id="gh-123",
        email="oauth@example.com",
        name="OAuth User",
        avatar_url="https://avatar",
        access_token="tok",
    )
    first = await auth.oauth_login(profile=profile, ctx=_CTX)
    assert first.access_token
    user = await auth.users.get_by_email("oauth@example.com")
    assert user is not None and user.is_verified is True

    # Returning login reuses the same account.
    second = await auth.oauth_login(profile=profile, ctx=_CTX)
    assert second.access_token
    again = await auth.users.get_by_email("oauth@example.com")
    assert again is not None and again.id == user.id


async def test_organization_rbac(session: AsyncSession) -> None:
    auth = AuthService(
        session, email_service=EmailService(provider=CapturingEmailProvider())
    )
    owner = await auth.register(
        email="owner@example.com", username="owner", password=_PASSWORD, display_name=None
    )
    org = await OrganizationService(session).create(name="Acme", owner_id=owner.id)

    rbac = RBACService(session)
    perms = await rbac.get_permissions_for_user(owner.id, org.id)
    assert "organization.manage" in perms
    await rbac.require_permission(owner.id, org.id, "member.manage")

    # A non-member has no permissions and is forbidden.
    outsider = await auth.register(
        email="out@example.com",
        username="outsider",
        password=_PASSWORD,
        display_name=None,
    )
    assert await rbac.get_permissions_for_user(outsider.id, org.id) == set()
    with pytest.raises(ForbiddenError):
        await rbac.require_permission(outsider.id, org.id, "member.manage")


async def test_invitation_flow(session: AsyncSession) -> None:
    cap = CapturingEmailProvider()
    email_service = EmailService(provider=cap)
    auth = AuthService(session, email_service=email_service)
    owner = await auth.register(
        email="o2@example.com", username="owner2", password=_PASSWORD, display_name=None
    )
    org = await OrganizationService(session).create(name="Beta", owner_id=owner.id)

    invitee = await auth.register(
        email="invitee@example.com",
        username="invitee",
        password=_PASSWORD,
        display_name=None,
    )
    inv_service = InvitationService(session, email_service=email_service)
    invitation, raw = await inv_service.invite(
        organization_id=org.id,
        email="invitee@example.com",
        role_slug=SystemRole.EDITOR.value,
        invited_by_id=owner.id,
        org_name=org.name,
    )
    assert invitation.status == "pending"

    await inv_service.accept(token=raw, user_id=invitee.id)
    perms = await RBACService(session).get_permissions_for_user(invitee.id, org.id)
    assert "video.create" in perms


async def test_api_key_lifecycle(session: AsyncSession) -> None:
    auth = AuthService(
        session, email_service=EmailService(provider=CapturingEmailProvider())
    )
    user = await auth.register(
        email="k@example.com", username="keyuser", password=_PASSWORD, display_name=None
    )
    service = ApiKeyService(session)
    # "video.create" is an RBAC permission, not an API scope. Scopes used to be
    # free text because nothing consumed them; they are now a validated
    # vocabulary. The lifecycle under test is unchanged.
    created = await service.create(user_id=user.id, name="ci", scopes=["video:read"])
    assert created.raw_key.startswith(created.api_key.prefix + ".")

    authed = await service.authenticate(created.raw_key)
    assert authed.id == created.api_key.id

    await service.revoke(user_id=user.id, key_id=created.api_key.id)
    with pytest.raises(UnauthorizedError):
        await service.authenticate(created.raw_key)

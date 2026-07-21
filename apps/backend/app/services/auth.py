"""Authentication service — the orchestration layer for the auth flows.

Coordinates repositories, the token service, RBAC, email, and audit logging to
implement registration, login, email verification, password reset, token
refresh, logout, and OAuth sign-in. No business logic lives in the API routes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions.base import ConflictError, UnauthorizedError, ValidationError
from app.models.auth import EmailVerificationToken, PasswordResetToken
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories.auth import (
    EmailVerificationTokenRepository,
    OAuthAccountRepository,
    PasswordResetTokenRepository,
)
from app.repositories.user import UserRepository
from app.security.password import hash_password, needs_rehash, verify_password
from app.security.tokens import generate_token, hash_token
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.login_guard import LoginGuard
from app.services.oauth import OAuthProfile
from app.services.token_service import IssuedTokens, RequestContext, TokenService
from app.utils.slug import slugify, unique_suffix

# A precomputed hash used to keep timing uniform when a user is not found.
_DUMMY_HASH = hash_password("Timing-Guard-Passw0rd!")


class AuthService:
    """Implements the authentication use cases."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        email_service: EmailService | None = None,
        login_guard: LoginGuard | None = None,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.email_tokens = EmailVerificationTokenRepository(session)
        self.reset_tokens = PasswordResetTokenRepository(session)
        self.oauth_accounts = OAuthAccountRepository(session)
        self.tokens = TokenService(session)
        self.audit = AuditService(session)
        self.email = email_service or EmailService()
        self.guard = login_guard or LoginGuard()

    # -- Registration -----------------------------------------------------
    async def register(
        self, *, email: str, username: str, password: str, display_name: str | None
    ) -> User:
        """Register a new user and send a verification email."""
        if await self.users.email_exists(email):
            raise ConflictError("An account with this email already exists.")
        if await self.users.username_exists(username):
            raise ConflictError("This username is already taken.")

        user = User(
            email=email.lower(),
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
            is_verified=False,
        )
        await self.users.add(user)
        await self._send_verification(user)
        await self.audit.record(AuditAction.USER_REGISTERED, actor_id=user.id)
        return user

    async def _send_verification(self, user: User) -> str:
        raw = generate_token()
        self.session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC)
                + timedelta(hours=settings.email_verification_expire_hours),
            )
        )
        await self.session.flush()
        await self.email.send_verification(to=user.email, token=raw)
        return raw

    async def verify_email(self, token: str) -> None:
        """Consume a verification token and mark the user verified."""
        record = await self.email_tokens.get_by_hash(hash_token(token))
        if record is None or record.used_at is not None:
            raise ValidationError("Invalid or already-used verification token.")
        if _expired(record.expires_at):
            raise ValidationError("Verification token has expired.")
        user = await self.users.get(record.user_id)
        if user is None:
            raise ValidationError("Invalid verification token.")
        user.is_verified = True
        record.used_at = datetime.now(UTC)
        await self.session.flush()
        await self.audit.record(AuditAction.EMAIL_VERIFIED, actor_id=user.id)

    # -- Login / logout ---------------------------------------------------
    async def login(
        self, *, email: str, password: str, ctx: RequestContext
    ) -> IssuedTokens:
        """Authenticate a user and issue tokens (email-enumeration safe)."""
        await self.guard.check(email)
        user = await self.users.get_by_email(email)

        # Always run a verify to equalize timing whether or not the user exists.
        candidate_hash = (
            user.password_hash if user and user.password_hash else _DUMMY_HASH
        )
        valid = verify_password(password, candidate_hash)

        if user is None or not valid or not user.password_hash:
            await self.guard.record_failure(email)
            if user is not None:
                await self.audit.record(
                    AuditAction.USER_LOGIN_FAILED,
                    actor_id=user.id,
                    ip_address=ctx.ip_address,
                )
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("This account is disabled.")

        # Transparent hash upgrade.
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        await self.guard.reset(email)
        return await self._issue_login(user, ctx, AuditAction.USER_LOGIN)

    async def _issue_login(
        self, user: User, ctx: RequestContext, action: AuditAction
    ) -> IssuedTokens:
        user.last_login = datetime.now(UTC)
        session = await self.tokens.create_session(user, ctx)
        issued = await self.tokens.issue_tokens(user, session)
        await self.audit.record(
            action,
            actor_id=user.id,
            ip_address=ctx.ip_address,
            target_type="session",
            target_id=str(session.id),
        )
        return issued

    async def logout(
        self, *, user: User, refresh_token: str | None, all_devices: bool
    ) -> None:
        """Revoke the current session, or all sessions for the user."""
        if all_devices:
            await self.tokens.revoke_all_for_user(user.id)
            await self.audit.record(AuditAction.SESSIONS_REVOKED_ALL, actor_id=user.id)
            return
        if refresh_token:
            record = await self.tokens.refresh_tokens.get_by_hash(
                hash_token(refresh_token)
            )
            if record is not None:
                await self.tokens.revoke_session(record.session_id)
        await self.audit.record(AuditAction.USER_LOGOUT, actor_id=user.id)

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        """Rotate a refresh token, returning a fresh token pair."""
        return await self.tokens.rotate(refresh_token)

    # -- Password reset ---------------------------------------------------
    async def forgot_password(self, email: str) -> None:
        """Issue a reset token if the account exists (always succeeds silently)."""
        user = await self.users.get_by_email(email)
        if user is None:
            return  # Do not reveal whether the email exists.
        raw = generate_token()
        self.session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC)
                + timedelta(hours=settings.password_reset_expire_hours),
            )
        )
        await self.session.flush()
        await self.email.send_password_reset(to=user.email, token=raw)
        await self.audit.record(AuditAction.PASSWORD_RESET_REQUESTED, actor_id=user.id)

    async def reset_password(self, *, token: str, new_password: str) -> None:
        """Consume a reset token, set the new password, and revoke all sessions."""
        record = await self.reset_tokens.get_by_hash(hash_token(token))
        if record is None or record.used_at is not None:
            raise ValidationError("Invalid or already-used reset token.")
        if _expired(record.expires_at):
            raise ValidationError("Reset token has expired.")
        user = await self.users.get(record.user_id)
        if user is None:
            raise ValidationError("Invalid reset token.")
        user.password_hash = hash_password(new_password)
        record.used_at = datetime.now(UTC)
        await self.tokens.revoke_all_for_user(user.id)
        await self.session.flush()
        await self.audit.record(AuditAction.PASSWORD_RESET, actor_id=user.id)

    async def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> None:
        """Change a logged-in user's password after verifying the current one."""
        if not user.password_hash or not verify_password(
            current_password, user.password_hash
        ):
            raise UnauthorizedError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        await self.session.flush()
        await self.audit.record(AuditAction.PASSWORD_CHANGED, actor_id=user.id)

    # -- OAuth ------------------------------------------------------------
    async def oauth_login(
        self, *, profile: OAuthProfile, ctx: RequestContext
    ) -> IssuedTokens:
        """Log in (or provision) a user from a normalized OAuth profile."""
        link = await self.oauth_accounts.get_by_provider(
            profile.provider.value, profile.account_id
        )
        if link is not None:
            user = await self.users.get(link.user_id)
            if user is None:
                raise UnauthorizedError("Linked account no longer exists.")
            self._sync_profile(user, profile)
        else:
            user = await self._link_or_create(profile)

        await self.session.flush()
        return await self._issue_login(user, ctx, AuditAction.OAUTH_LOGIN)

    async def _link_or_create(self, profile: OAuthProfile) -> User:
        from app.models.auth import OAuthAccount

        user = await self.users.get_by_email(profile.email) if profile.email else None
        if user is None:
            username = slugify(profile.name or (profile.email or "user").split("@")[0])
            if await self.users.username_exists(username):
                username = f"{username}-{unique_suffix()}"
            user = User(
                email=(
                    profile.email
                    or f"{profile.account_id}@{profile.provider.value}.oauth"
                ),
                username=username,
                display_name=profile.name,
                avatar_url=profile.avatar_url,
                is_active=True,
                is_verified=bool(profile.email),
            )
            await self.users.add(user)
        else:
            self._sync_profile(user, profile)

        self.session.add(
            OAuthAccount(
                user_id=user.id,
                provider=profile.provider.value,
                provider_account_id=profile.account_id,
                email=profile.email,
                access_token=profile.access_token,
            )
        )
        await self.session.flush()
        return user

    @staticmethod
    def _sync_profile(user: User, profile: OAuthProfile) -> None:
        if profile.avatar_url and not user.avatar_url:
            user.avatar_url = profile.avatar_url
        if profile.name and not user.display_name:
            user.display_name = profile.name


def _expired(expires_at: datetime) -> bool:
    """Return True if ``expires_at`` (possibly naive on SQLite) is past."""
    reference = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    return reference < datetime.now(UTC)

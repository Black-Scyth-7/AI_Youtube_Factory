"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.config import settings
from app.dependencies.auth import CurrentUser, DbSession, RequestCtx
from app.models.enums import OAuthProvider
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserResponse
from app.security.oauth_state import issue_state, verify_state
from app.services.auth import AuthService
from app.services.oauth import get_oauth_client

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(issued) -> TokenResponse:  # type: ignore[no-untyped-def]
    return TokenResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
    )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(body: RegisterRequest, session: DbSession) -> UserResponse:
    """Register a new account and send a verification email."""
    user = await AuthService(session).register(
        email=body.email,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: DbSession, ctx: RequestCtx) -> TokenResponse:
    """Authenticate and receive an access/refresh token pair."""
    issued = await AuthService(session).login(
        email=body.email, password=body.password, ctx=ctx
    )
    return _tokens(issued)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: DbSession) -> TokenResponse:
    """Rotate a refresh token, returning a new token pair."""
    issued = await AuthService(session).refresh(body.refresh_token)
    return _tokens(issued)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: LogoutRequest, user: CurrentUser, session: DbSession
) -> MessageResponse:
    """Revoke the current session, or all sessions when ``all_devices`` is set."""
    await AuthService(session).logout(
        user=user, refresh_token=body.refresh_token, all_devices=body.all_devices
    )
    return MessageResponse(message="Logged out.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest, session: DbSession) -> MessageResponse:
    """Verify an email address using a one-time token."""
    await AuthService(session).verify_email(body.token)
    return MessageResponse(message="Email verified.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest, session: DbSession
) -> MessageResponse:
    """Request a password reset link (always returns success)."""
    await AuthService(session).forgot_password(body.email)
    return MessageResponse(
        message="If an account exists for that email, a reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest, session: DbSession
) -> MessageResponse:
    """Reset a password using a one-time token."""
    await AuthService(session).reset_password(
        token=body.token, new_password=body.password
    )
    return MessageResponse(message="Password has been reset.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest, user: CurrentUser, session: DbSession
) -> MessageResponse:
    """Change the current user's password."""
    await AuthService(session).change_password(
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return MessageResponse(message="Password changed.")


# -- OAuth ---------------------------------------------------------------
@router.get("/{provider}/authorize")
async def oauth_authorize(provider: OAuthProvider) -> dict[str, str]:
    """Return the provider authorization URL to redirect the user to."""
    client = get_oauth_client(provider)
    state = issue_state(provider.value)
    return {"authorization_url": client.authorization_url(state)}


@router.get("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: OAuthProvider,
    code: str,
    state: str,
    session: DbSession,
    ctx: RequestCtx,
) -> TokenResponse:
    """Handle the OAuth callback: verify state, exchange code, and sign in."""
    verify_state(state, provider.value)
    client = get_oauth_client(provider)
    profile = await client.exchange_code(code)
    issued = await AuthService(session).oauth_login(profile=profile, ctx=ctx)
    return _tokens(issued)


# Expose the configured frontend URL for clients that build their own links.
@router.get("/config")
async def auth_config() -> dict[str, object]:
    """Return non-secret auth configuration for the frontend."""
    return {
        "frontend_url": settings.frontend_url,
        "providers": [p.value for p in OAuthProvider],
    }

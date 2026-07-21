"""Google OAuth 2.0 client."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import settings
from app.exceptions.base import ServiceUnavailableError, UnauthorizedError
from app.models.enums import OAuthProvider
from app.services.oauth.base import OAuthClient, OAuthProfile

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient(OAuthClient):
    """Google identity provider."""

    provider = OAuthProvider.GOOGLE

    def _require_config(self) -> tuple[str, str]:
        if not settings.google_client_id or not settings.google_client_secret:
            raise ServiceUnavailableError("Google OAuth is not configured.")
        return settings.google_client_id, settings.google_client_secret

    def authorization_url(self, state: str) -> str:
        client_id, _ = self._require_config()
        params = {
            "client_id": client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthProfile:
        client_id, client_secret = self._require_config()
        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.post(
                _TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code != 200:
                raise UnauthorizedError("Google authorization failed.")
            access_token = token_res.json()["access_token"]

            info_res = await client.get(
                _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            if info_res.status_code != 200:
                raise UnauthorizedError("Failed to fetch Google profile.")
            info = info_res.json()

        return OAuthProfile(
            provider=OAuthProvider.GOOGLE,
            account_id=str(info["sub"]),
            email=info.get("email"),
            name=info.get("name"),
            avatar_url=info.get("picture"),
            access_token=access_token,
        )

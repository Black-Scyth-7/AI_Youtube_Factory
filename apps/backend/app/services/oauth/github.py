"""GitHub OAuth 2.0 client."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import settings
from app.exceptions.base import ServiceUnavailableError, UnauthorizedError
from app.models.enums import OAuthProvider
from app.services.oauth.base import OAuthClient, OAuthProfile

_AUTH_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubOAuthClient(OAuthClient):
    """GitHub identity provider."""

    provider = OAuthProvider.GITHUB

    def _require_config(self) -> tuple[str, str]:
        if not settings.github_client_id or not settings.github_client_secret:
            raise ServiceUnavailableError("GitHub OAuth is not configured.")
        return settings.github_client_id, settings.github_client_secret

    def authorization_url(self, state: str) -> str:
        client_id, _ = self._require_config()
        params = {
            "client_id": client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthProfile:
        client_id, client_secret = self._require_config()
        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.post(
                _TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": settings.github_redirect_uri,
                },
            )
            if token_res.status_code != 200 or "access_token" not in token_res.json():
                raise UnauthorizedError("GitHub authorization failed.")
            access_token = token_res.json()["access_token"]

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            }
            user_res = await client.get(_USER_URL, headers=headers)
            if user_res.status_code != 200:
                raise UnauthorizedError("Failed to fetch GitHub profile.")
            user = user_res.json()

            email = user.get("email")
            if not email:
                emails_res = await client.get(_EMAILS_URL, headers=headers)
                if emails_res.status_code == 200:
                    primary = next(
                        (e for e in emails_res.json() if e.get("primary")), None
                    )
                    email = primary["email"] if primary else None

        return OAuthProfile(
            provider=OAuthProvider.GITHUB,
            account_id=str(user["id"]),
            email=email,
            name=user.get("name") or user.get("login"),
            avatar_url=user.get("avatar_url"),
            access_token=access_token,
        )

"""User and profile repositories."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.user import Profile, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access for :class:`User`."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Return an active (not soft-deleted) user by case-insensitive email."""
        result = await self.session.execute(
            select(User).where(
                func.lower(User.email) == email.lower(), User.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Return a user by case-insensitive username."""
        result = await self.session.execute(
            select(User).where(
                func.lower(User.username) == username.lower(),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return (await self.get_by_email(email)) is not None

    async def username_exists(self, username: str) -> bool:
        return (await self.get_by_username(username)) is not None


class ProfileRepository(BaseRepository[Profile]):
    """Data access for :class:`Profile`."""

    model = Profile

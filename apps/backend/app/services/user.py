"""User profile service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import NotFoundError
from app.models.user import Profile, User
from app.repositories.user import ProfileRepository, UserRepository


class UserService:
    """Reads and updates user and profile records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)

    async def update_user(self, user: User, **fields: object) -> User:
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value)
        await self.session.flush()
        return user

    async def get_or_create_profile(self, user_id: uuid.UUID) -> Profile:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.profile is not None:
            return user.profile
        profile = Profile(user_id=user_id)
        return await self.profiles.add(profile)

    async def update_profile(self, user_id: uuid.UUID, **fields: object) -> Profile:
        profile = await self.get_or_create_profile(user_id)
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.session.flush()
        return profile

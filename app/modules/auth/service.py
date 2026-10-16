import uuid

import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import create_token, decode_token
from app.modules.auth.providers.base import AuthProvider
from app.modules.auth.schemas import TokenPair
from app.modules.users.repository import UserRepository


class AuthService:
    def __init__(self, repo: UserRepository, provider: AuthProvider):
        self.repo = repo
        self.provider = provider

    async def login(self, staff_id: str, password: str) -> TokenPair:
        user = await self.provider.authenticate(staff_id=staff_id, password=password)
        if not user or not user.is_active:
            raise UnauthorizedError("Invalid staff ID or password")
        return self._issue(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            user_id = decode_token(refresh_token, "refresh")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid or expired refresh token")
        user = await self.repo.get(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User inactive or not found")
        return self._issue(user.id)

    @staticmethod
    def _issue(user_id: uuid.UUID) -> TokenPair:
        return TokenPair(
            access_token=create_token(user_id, "access"),
            refresh_token=create_token(user_id, "refresh"),
        )
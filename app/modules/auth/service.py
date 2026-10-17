import uuid

import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import create_token, decode_payload
from app.modules.auth.providers.base import AuthProvider
from app.modules.auth.revocation import consume, is_session_revoked, revoke_session
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
        return self._issue(user.id, user.staff_id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_payload(refresh_token, "refresh")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Invalid or expired refresh token")
        if await is_session_revoked(payload["sid"]):
            raise UnauthorizedError("Session has ended")

        user = await self.repo.get(uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise UnauthorizedError("User inactive or not found")

        if not await consume(payload):  # reused token: assume it was stolen
            await revoke_session(payload["sid"])
            raise UnauthorizedError("Refresh token already used")

        return self._issue(user.id, user.staff_id, sid=payload["sid"])

    async def logout(self, sid: str) -> None:
        await revoke_session(sid)

    @staticmethod
    def _issue(user_id: uuid.UUID, sid: str) -> TokenPair:
        sid = sid or str(uuid.uuid4())
        return TokenPair(
            access_token=create_token(user_id, "access", sid),
            refresh_token=create_token(user_id, "refresh", sid),
        )

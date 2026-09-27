import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import create_token, decode_token, verify_password
from app.modules.auth.schemas import TokenPair
from app.modules.users.repository import UserRepository


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.repo.get_by_email(email)
        # same message for both cases -> don't reveal which emails exist
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
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
    def _issue(user_id) -> TokenPair:
        return TokenPair(
            access_token=create_token(user_id, "access"),
            refresh_token=create_token(user_id, "refresh"),
        )

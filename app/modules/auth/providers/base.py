from typing import Protocol

from app.modules.users.models import User


class AuthProvider(Protocol):
    async def authenticate(self, staff_id: str, password: str) -> User | None: ...
import secrets
from app.core.config import get_settings
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

class LocalAuthProvider:
    """Testing only: any existing staff ID + the shared default password."""

    def __init__(self, users: UserRepository):
        self.users = users

    async def authenticate(self, staff_id: str, password: str) -> User | None:
        if not secrets.compare_digest(password, get_settings().DEFAULT_PASSWORD):
            return None
        return await self.users.get_by_staff_id(staff_id)
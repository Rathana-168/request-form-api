# import uuid
from typing import Annotated

# import jwt
from fastapi import Depends, Header
# from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, UnauthorizedError
# from app.core.security import decode_token
from app.db.session import get_db
from app.modules.users.models import User
from app.core.config import get_settings

DbSession = Annotated[AsyncSession, Depends(get_db)]

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    db: DbSession, 
    # token: Annotated[str, Depends(oauth2_scheme)],
    cif: Annotated[str | None, Header()] = None,
) -> User:
    if not cif:
        raise UnauthorizedError("Missing CIF header")
    
    # try:
    #     user_id: uuid.UUID = decode_token(token, "access")
    # except jwt.InvalidTokenError:
    #     raise UnauthorizedError("Invalid or expired token")
    lookup_col = getattr(User, get_settings().CIF_LOOKUP_FIELD)
    user = await db.scalar(select(User).where(lookup_col == cif))
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive or not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*codes: str):
    async def checker(user: CurrentUser) -> User:
        if user.is_superuser or set(codes) <= user.permission_codes:
            return user
        raise PermissionDeniedError(f"Missing permission: {', '.join(codes)}")

    return checker

import uuid
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.context import current_user_id
from app.core.exceptions import PermissionDeniedError, UnauthorizedError
from app.core.security import decode_payload
from app.db.session import get_db
from app.modules.auth.revocation import is_session_revoked
from app.modules.users.models import Role, User

DbSession = Annotated[AsyncSession, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_token_payload(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict:
    if not token:
        raise UnauthorizedError("Not authenticated")
    try:
        payload = decode_payload(token, "access")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid or expired token")
    
    if await is_session_revoked(payload["sid"]):
        raise UnauthorizedError("Session logged out")
    return payload


TokenPayload = Annotated[dict, Depends(get_token_payload)]


async def get_current_user(db: DbSession, payload: TokenPayload) -> User:
    user = await db.scalar(
        select(User)
        .where(User.id == uuid.UUID(payload["sub"]))
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive or not found")
    current_user_id.set(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*codes: str):
    async def checker(user: CurrentUser) -> User:
        if user.is_superuser or set(codes) <= user.permission_codes:
            return user
        raise PermissionDeniedError(f"Missing permission: {', '.join(codes)}")

    return checker
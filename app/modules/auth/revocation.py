import time

from app.core.config import get_settings
from app.integrations.redis import get_redis


PREFIX = "auth:revoked:"
SESSION_PREFIX = "auth:session-revoked:"


async def revoke(payload: dict) -> None:
    ttl = int(payload["exp"] - time.time())
    if ttl > 0:
        await get_redis().set(PREFIX + payload["jti"], "1", ex=ttl)

async def is_revoked(jti: str) -> bool:
    return await get_redis().exists(PREFIX + jti) == 1


async def revoke_session(sid: str) -> None:
    ttl = get_settings().REFRESH_TOKEN_EXPIRE_DAYS * 86400   # outlives any token of this session
    await get_redis().set(SESSION_PREFIX + sid, "1", ex=ttl)


async def is_session_revoked(sid: str) -> bool:
    return await get_redis().exists(SESSION_PREFIX + sid) == 1
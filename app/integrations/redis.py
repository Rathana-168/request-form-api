from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, RedisError, TimeoutError
from redis.retry import Retry

from app.core.config import get_settings
from app.core.logging import get_logger


log = get_logger(__name__)

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        s = get_settings()
        _client = Redis.from_url(
            s.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=s.REDIS_CONNECT_TIMEOUT,  # fail fast if Redis is down
            socket_timeout=s.REDIS_SOCKET_TIMEOUT,           # don't hang on a stuck command
            retry=Retry(ExponentialBackoff(cap=0.5, base=0.05), retries=s.REDIS_RETRIES),
            retry_on_error=[ConnectionError, TimeoutError],
            health_check_interval=30,                        # re-check idle connections
            max_connections=s.REDIS_MAX_CONNECTIONS,
        )
    return _client


async def ping_redis() -> bool:
    """For readiness checks: True if Redis answers, never raises."""
    try:
        return await get_redis().ping()
    except RedisError as e:
        log.warning("Redis ping failed: %s", e)
        return False


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
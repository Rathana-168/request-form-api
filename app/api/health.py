import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import engine  # your async engine
from app.integrations.redis import ping_redis

log = get_logger(__name__)

router = APIRouter(include_in_schema=False)

TIMEOUT = 2.0


async def _db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _redis() -> None:
    if not await ping_redis():               # adjust if ping_redis raises instead
        raise RuntimeError("ping failed")


async def _check(name: str, fn) -> tuple[str, bool]:
    try:
        await asyncio.wait_for(fn(), TIMEOUT)
        return name, True
    except Exception as e:
        log.warning("readiness check %s failed: %r", name, e)
        return name, False


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    results = dict(await asyncio.gather(
        _check("database", _db), 
        _check("redis", _redis)
    ))
    ok = all(results.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not_ready",
            "checks": {k: "ok" if v else "fail" for k, v in results.items()},
        },
    )
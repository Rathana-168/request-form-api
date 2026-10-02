import logging
from collections import Counter
from contextvars import ContextVar

from fastapi import FastAPI, Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)

_box: ContextVar[list[str] | None] = ContextVar("query_box", default=None)


def _collect(conn, cursor, statement, *_args) -> None:
    box = _box.get()
    if box is not None:
        box.append(" ".join(statement.split())[:120])


def _summary(box: list[str], top: int = 8) -> str:
    lines = [f"{n:>3} x {sql}" for sql, n in Counter(box).most_common(top)]
    return f"{len(box)} queries\n" + "\n".join(lines)


def install(app: FastAPI, engine: AsyncEngine) -> None:
    """Count and summarise SQL per request. Call only in development."""
    event.listen(engine.sync_engine, "before_cursor_execute", _collect)

    @app.middleware("http")
    async def count_queries(request: Request, call_next):
        box: list[str] = []
        token = _box.set(box)
        try:
            return await call_next(request)
        finally:
            _box.reset(token)
            log.info("%s %s → %s", request.method, request.url.path, _summary(box))
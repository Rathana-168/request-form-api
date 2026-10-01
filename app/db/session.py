from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

def _engine_options() -> dict[str, Any]:
    """Shared by the API engine and task engines, so both see the same schema."""
    return {
        "echo": settings.DEBUG,
        "connect_args": {"server_settings": {"search_path": settings.DATABASE_SCHEMA}},
    }

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    **_engine_options()
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------- Celery tasks: a fresh engine per run ----------
@asynccontextmanager
async def task_sessions() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    """Session factory for one task run.

    Each Celery run calls asyncio.run (a new event loop), and pooled asyncpg
    connections can't move between loops, so tasks get their own short-lived engine.
    """
    task_engine = create_async_engine(
        settings.DATABASE_URL, 
        poolclass=NullPool, 
        **_engine_options()
    )
    try:
        yield async_sessionmaker(task_engine, expire_on_commit=False)
    finally:
        await task_engine.dispose()
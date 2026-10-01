import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add_many(self, items: list[Notification]) -> None:
        self.db.add_all(items)

    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int, limit: int, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def unread_count(self, user_id: uuid.UUID) -> int:
        count = await self.db.scalar(
            select(func.count()).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
        return count or 0

    async def mark_read(self, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
        stmt = update(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
        if ids:
            stmt = stmt.where(Notification.id.in_(ids))
        await self.db.execute(stmt.values(read_at=func.now()))
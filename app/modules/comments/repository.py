import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.models import RequestComment


class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add(self, comment: RequestComment) -> None:
        self.db.add(comment)

    async def get(self, comment_id: uuid.UUID) -> RequestComment | None:
        return await self.db.get(RequestComment, comment_id)

    async def list_for_request(
        self, request_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[RequestComment], int]:
        stmt = select(RequestComment).where(RequestComment.request_id == request_id)
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(RequestComment.created_at).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def count_for_request(self, request_id: uuid.UUID) -> int:
        count = await self.db.scalar(
            select(func.count()).where(
                RequestComment.request_id == request_id,
                RequestComment.deleted_at.is_(None),
            )
        )
        return count or 0

    async def commenter_ids(self, request_id: uuid.UUID) -> list[uuid.UUID]:
        """Everyone who has commented, for notifications."""
        rows = await self.db.scalars(
            select(RequestComment.author_id).distinct().where(
                RequestComment.request_id == request_id,
                RequestComment.author_id.is_not(None),
            )
        )
        return list(rows)
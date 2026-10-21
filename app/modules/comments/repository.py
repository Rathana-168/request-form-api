import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
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
    ) -> tuple[list[tuple[RequestComment, int, datetime | None]], int]:
        replies = (
            select(
                RequestComment.parent_id.label("pid"),
                func.count().label("reply_count"),
                func.max(RequestComment.created_at).label("last_reply_at"),
            )
            .where(
                RequestComment.request_id == request_id,
                RequestComment.parent_id.is_not(None),
                RequestComment.deleted_at.is_(None),
            )
            .group_by(RequestComment.parent_id)
            .subquery()
        )
        reply_count = func.coalesce(replies.c.reply_count, 0)
        stmt = (
            select(RequestComment, reply_count, replies.c.last_reply_at)
            .outerjoin(replies, replies.c.pid == RequestComment.id)
            .where(
                RequestComment.request_id == request_id,
                RequestComment.parent_id.is_(None),
                # hide deleted parents that have no thread left
                or_(RequestComment.deleted_at.is_(None), reply_count > 0),
            )
        )
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.execute(
            stmt.order_by(RequestComment.created_at).offset(offset).limit(limit)
        )
        return [tuple(r) for r in rows.all()], total or 0

    async def count_for_request(self, request_id: uuid.UUID) -> int:
        count = await self.db.scalar(
            select(func.count()).where(
                RequestComment.request_id == request_id,
                RequestComment.deleted_at.is_(None),
            )
        )
        return count or 0

    async def commenter_ids(self, request_id: uuid.UUID) -> list[uuid.UUID | None]:
        """Everyone who has commented, for notifications."""
        rows = await self.db.scalars(
            select(RequestComment.author_id).distinct().where(
                RequestComment.request_id == request_id,
                RequestComment.author_id.is_not(None),
            )
        )
        return list(rows)
    
    async def list_replies(
        self, parent_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[RequestComment], int]:
        stmt = select(RequestComment).where(
            RequestComment.parent_id == parent_id,
            RequestComment.deleted_at.is_(None),
        )
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(RequestComment.created_at).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def thread_participant_ids(self, parent_id: uuid.UUID) -> list[uuid.UUID | None]:
        """Parent author and everyone who replied, for Step 3 notifications."""
        rows = await self.db.scalars(
            select(RequestComment.author_id).distinct().where(
                or_(RequestComment.id == parent_id, RequestComment.parent_id == parent_id),
                RequestComment.author_id.is_not(None),
            )
        )
        return list(rows)

    async def counts_for_requests(self, request_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not request_ids:
            return {}
        rows = await self.db.execute(
            select(RequestComment.request_id, func.count())
            .where(
                RequestComment.request_id.in_(request_ids),
                RequestComment.deleted_at.is_(None),
            )
            .group_by(RequestComment.request_id)
        )
        return {rid: n for rid, n in rows.all()}
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.requests.models import Request


class ApprovalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, task_id: uuid.UUID) -> ApprovalTask | None:
        return await self.db.get(ApprovalTask, task_id)

    async def inbox(
        self, user_id: uuid.UUID, *, offset: int, limit: int, form_code: str | None
    ) -> tuple[list[tuple[ApprovalTask, Request]], int]:
        stmt = (
            select(ApprovalTask, Request)
            .join(Request, Request.id == ApprovalTask.request_id)
            .where(ApprovalTask.assignee_id == user_id, ApprovalTask.status == TaskStatus.PENDING)
        )
        if form_code:
            stmt = stmt.where(Request.form_code == form_code)
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.execute(
            stmt.order_by(ApprovalTask.created_at).offset(offset).limit(limit)
        )
        return [tuple(r) for r in rows], total or 0

    async def for_request(self, request_id: uuid.UUID) -> list[ApprovalTask]:
        rows = await self.db.scalars(
            select(ApprovalTask)
            .where(ApprovalTask.request_id == request_id)
            .order_by(ApprovalTask.created_at, ApprovalTask.step_no)
        )
        return list(rows)

    async def is_assignee(self, request_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        found = await self.db.scalar(
            select(ApprovalTask.id)
            .where(ApprovalTask.request_id == request_id, ApprovalTask.assignee_id == user_id)
            .limit(1)
        )
        return found is not None
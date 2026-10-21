import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.models import ApprovalProxy, ApprovalTask, TaskStatus
from app.modules.requests.models import Request


class ApprovalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, task_id: uuid.UUID) -> ApprovalTask | None:
        return await self.db.get(ApprovalTask, task_id)

    async def inbox(
        self,
        user_id: uuid.UUID,
        *,
        acting_ids: list[uuid.UUID],
        offset: int,
        limit: int,
        form_code: str | None,
    ) -> tuple[list[tuple[ApprovalTask, Request]], int]:
        stmt = (
            select(ApprovalTask, Request)
            .join(Request, Request.id == ApprovalTask.request_id)
            .where(
                ApprovalTask.status == TaskStatus.PENDING,
                # as a proxy, never show your own request
                or_(ApprovalTask.assignee_id == user_id, Request.requester_id != user_id),
            )
        )
        if len(acting_ids) > 1:  # acting as a proxy for someone
            # never show the proxy their own request through someone else's task
            stmt = stmt.where(
                or_(ApprovalTask.assignee_id == user_id, Request.requester_id != user_id)
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

    async def can_view(self, request_id: uuid.UUID, acting_ids: list[uuid.UUID]) -> bool:
        found = await self.db.scalar(
            select(ApprovalTask.id).where(
                ApprovalTask.request_id == request_id,
                ApprovalTask.assignee_id.in_(acting_ids),  # mine, or my active principal's
            ).limit(1)
        )
        return found is not None
    
    async def pending_approval_tasks(self, request_id: uuid.UUID) -> list[ApprovalTask]:
        return list(await self.db.scalars(
            select(ApprovalTask).where(
                ApprovalTask.request_id == request_id,
                ApprovalTask.status == TaskStatus.PENDING,
            )
        ))


def _active_at(now: datetime):
    return and_(
        ApprovalProxy.ended_at.is_(None),
        ApprovalProxy.start_at <= now,
        ApprovalProxy.end_at > now,
    )


class ApprovalProxyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add(self, proxy: ApprovalProxy) -> None:
        self.db.add(proxy)

    async def principals_of(self, proxy_id: uuid.UUID, now: datetime) -> list[uuid.UUID]:
        """People whose tasks this user may currently act on."""
        rows = await self.db.scalars(
            select(ApprovalProxy.principal_id).where(
                ApprovalProxy.proxy_id == proxy_id, _active_at(now)
            )
        )
        return list(rows)

    async def proxies_of(self, principal_id: uuid.UUID, now: datetime) -> list[uuid.UUID]:
        """People who may currently act on this user's tasks."""
        rows = await self.db.scalars(
            select(ApprovalProxy.proxy_id).where(
                ApprovalProxy.principal_id == principal_id, _active_at(now)
            )
        )
        return list(rows)

    async def can_act_for(
        self, proxy_id: uuid.UUID, principal_id: uuid.UUID, now: datetime
    ) -> bool:
        found = await self.db.scalar(
            select(ApprovalProxy.id).where(
                ApprovalProxy.proxy_id == proxy_id,
                ApprovalProxy.principal_id == principal_id,
                _active_at(now),
            ).limit(1)
        )
        return found is not None

    async def current_for(self, user_id: uuid.UUID, now: datetime) -> list[ApprovalProxy]:
        """Running or scheduled proxies where the user is principal or proxy."""
        rows = await self.db.scalars(
            select(ApprovalProxy)
            .where(
                or_(ApprovalProxy.principal_id == user_id, ApprovalProxy.proxy_id == user_id),
                ApprovalProxy.ended_at.is_(None),
                ApprovalProxy.end_at > now,
            )
            .order_by(ApprovalProxy.start_at)
        )
        return list(rows)

    async def open_by_source(self, request_id: uuid.UUID) -> ApprovalProxy | None:
        return await self.db.scalar(select(ApprovalProxy).where(
            ApprovalProxy.source_request_id == request_id,
            ApprovalProxy.ended_at.is_(None),
        ))
    
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.forms.plugin import FormDataMixin
from app.modules.requests.models import (
    Request,
    RequestCounter,
    RequestHistory,
    RequestStatus,
)


class RequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, request_id: uuid.UUID, *, for_update: bool = False) -> Request | None:
        stmt = select(Request).where(Request.id == request_id)
        if for_update:
            stmt = stmt.with_for_update(of=Request)  # serialise submit/cancel on one request
        return await self.db.scalar(stmt)

    async def list_for_requester(
        self,
        requester_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        status: RequestStatus | None,
        form_code: str | None,
    ) -> tuple[list[Request], int]:
        stmt = select(Request).where(Request.requester_id == requester_id)
        if status:
            stmt = stmt.where(Request.status == status)
        if form_code:
            stmt = stmt.where(Request.form_code == form_code)

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(Request.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def add(self, request: Request) -> Request:
        self.db.add(request)
        await self.db.flush()
        return request

    async def delete(self, request: Request) -> None:
        await self.db.delete(request)  # form row + history go via ON DELETE CASCADE
        await self.db.flush()

    # --- form data (the plugin's own table) ---

    async def get_data[T: FormDataMixin](self, model: type[T], request_id: uuid.UUID) -> T | None:
        return await self.db.scalar(select(model).where(model.request_id == request_id).options(selectinload("*")))

    async def add_data(self, row: FormDataMixin) -> None:
        self.db.add(row)
        await self.db.flush()

    # --- history ---

    async def add_history(self, entry: RequestHistory) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_history(self, request_id: uuid.UUID) -> list[RequestHistory]:
        rows = await self.db.scalars(
            select(RequestHistory)
            .where(RequestHistory.request_id == request_id)
            .order_by(RequestHistory.created_at)
        )
        return list(rows)

    # --- numbering ---

    async def next_request_no(self, prefix: str) -> str:
        """Atomic per-prefix-per-year counter: LEAVE-2026-00001."""
        key = f"{prefix}-{datetime.now(UTC).year}"
        stmt = (
            insert(RequestCounter)
            .values(key=key, value=1)
            .on_conflict_do_update(
                index_elements=[RequestCounter.key],
                set_={"value": RequestCounter.value + 1},
            )
            .returning(RequestCounter.value)
        )
        value = await self.db.scalar(stmt)
        return f"{key}-{value:05d}"
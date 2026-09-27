import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forms.models import Form


class FormRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, form_id: uuid.UUID) -> Form | None:
        return await self.db.get(Form, form_id)

    async def get_by_code(self, code: str) -> Form | None:
        return await self.db.scalar(select(Form).where(Form.code == code))

    async def list_codes(self) -> set[str]:
        return set(await self.db.scalars(select(Form.code)))

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        active_only: bool,
        search: str | None = None,
        category: str | None = None,
    ) -> tuple[list[Form], int]:
        stmt = select(Form)
        if active_only:
            stmt = stmt.where(Form.is_active.is_(True))
        if category:
            stmt = stmt.where(Form.category == category)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Form.name.ilike(like), Form.code.ilike(like)))

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(Form.name).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def add(self, form: Form) -> Form:
        self.db.add(form)
        await self.db.flush()
        await self.db.refresh(form)
        return form

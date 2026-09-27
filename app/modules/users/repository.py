import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User
from app.modules.users.models import Department  # add to imports


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return await self.db.scalar(stmt)

    async def list(
        self, *, offset: int, limit: int, search: str | None = None
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.scalars(
            stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows), total or 0

    async def add(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()  # get the id without committing
        await self.db.refresh(user)
        return user

    async def get_roles(self, role_ids: list[uuid.UUID]) -> list[Role]:
        if not role_ids:
            return []
        return list(await self.db.scalars(select(Role).where(Role.id.in_(role_ids))))

    async def get_department(self, dept_id: uuid.UUID) -> Department | None:
        return await self.db.get(Department, dept_id)

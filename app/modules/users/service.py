import uuid

from app.core.security import hash_password
from app.modules.users.exceptions import (
    EmailAlreadyExistsError,
    InvalidManagerError,
    InvalidReferenceError,
    StaffIdAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate
from app.shared.schemas import Page, PageParams


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def list(self, params: PageParams, search: str | None) -> Page:
        items, total = await self.repo.list(
            offset=params.offset, limit=params.size, search=search
        )
        return Page(items=items, total=total, page=params.page, size=params.size)

    async def create(self, data: UserCreate) -> User:
        if await self.repo.get_by_email(data.email):
            raise EmailAlreadyExistsError()

        await self._check_department(data.department_id)
        if data.manager_id:
            await self.get(data.manager_id)  # must exist

        user = User(
            staff_id=data.staff_id,
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            department_id=data.department_id,
            manager_id=data.manager_id,
            roles=await self._load_roles(data.role_ids)
        )
        return await self.repo.add(user)

    async def update(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = await self.get(user_id)
        changes = data.model_dump(exclude_unset=True)
        
        if changes.get("staff_id") and changes["staff_id"] != user.staff_id:
            if await self.repo.get_by_staff_id(changes["staff_id"]):
                raise StaffIdAlreadyExistsError()

        if "department_id" in changes:
            await self._check_department(changes["department_id"])
        if "manager_id" in changes:
            await self._check_manager(user, changes["manager_id"])
        if "role_ids" in changes:
            await self.repo.db.refresh(user, attribute_names=["roles"])
            user.roles = await self._load_roles(changes.pop("role_ids"))

        for field, value in changes.items():
            setattr(user, field, value)
        return user

    # ---- rules ----
    async def _check_department(self, dept_id: uuid.UUID | None) -> None:
        if dept_id and not await self.repo.get_department(dept_id):
            raise InvalidReferenceError("Department not found")

    async def _load_roles(self, role_ids: list[uuid.UUID]):
        roles = await self.repo.get_roles(role_ids)
        if len(roles) != len(set(role_ids)):
            raise InvalidReferenceError("One or more roles not found")
        return roles

    async def _check_manager(self, user: User, manager_id: uuid.UUID | None) -> None:
        """Block self-management and reporting loops (A→B→A)."""
        current_id = manager_id
        while current_id:
            if current_id == user.id:
                raise InvalidManagerError("Manager assignment creates a loop")
            manager = await self.get(current_id)
            current_id = manager.manager_id

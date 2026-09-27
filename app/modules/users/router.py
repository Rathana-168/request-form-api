import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_permission
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserOut, UserUpdate
from app.modules.users.service import UserService
from app.shared.schemas import APIResponse, Page, PageParams

router = APIRouter()


def get_user_service(db: DbSession) -> UserService:
    return UserService(UserRepository(db))


UserSvc = Annotated[UserService, Depends(get_user_service)]


@router.get(
    "",
    response_model=APIResponse[Page[UserOut]],
    dependencies=[Depends(require_permission("user:read"))],
)
async def list_users(
    svc: UserSvc,
    params: Annotated[PageParams, Depends()],
    search: Annotated[str | None, Query(max_length=100)] = None,
):
    return APIResponse.success(await svc.list(params, search))


@router.get(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_permission("user:read"))],
)
async def get_user(user_id: uuid.UUID, svc: UserSvc):
    return await svc.get(user_id)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("user:create"))],
)
async def create_user(data: UserCreate, svc: UserSvc):
    return await svc.create(data)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_permission("user:update"))],
)
async def update_user(user_id: uuid.UUID, data: UserUpdate, svc: UserSvc):
    return await svc.update(user_id, data)

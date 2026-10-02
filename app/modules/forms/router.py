import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, require_permission

from app.modules.forms.repository import FormRepository
from app.modules.forms.schemas import FormCreate, FormOut, FormUpdate
from app.modules.forms.service import FormService
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams, ok, APIResponse

router = APIRouter()


def get_form_service(db: DbSession) -> FormService:
    return FormService(FormRepository(db))


FormSvc = Annotated[FormService, Depends(get_form_service)]
FormManager = Annotated[User, Depends(require_permission("form:manage"))]


@router.get("", response_model=APIResponse[Page[FormOut]])
async def list_forms(
    user: CurrentUser,
    svc: FormSvc,
    params: Annotated[PageParams, Depends()],
    search: Annotated[str | None, Query(max_length=100)] = None,
    category: str | None = None,
    include_inactive: bool = False,
):
    can_manage = user.is_superuser or "form:manage" in user.permission_codes
    return ok(await svc.list(
        params,
        active_only=not (include_inactive and can_manage),
        search=search,
        category=category,
    ))


@router.get("/available-codes", response_model=APIResponse[list[str]])
async def available_codes(_: FormManager, svc: FormSvc):
    return ok(await svc.available_codes(), message="Available code need to add to Form")


@router.get("/{form_id}", response_model=APIResponse[FormOut])
async def get_form(form_id: uuid.UUID, _: CurrentUser, svc: FormSvc):
    return ok(await svc.get(form_id))


@router.post("", response_model=APIResponse[FormOut], status_code=status.HTTP_201_CREATED)
async def create_form(data: FormCreate, user: FormManager, svc: FormSvc):
    return ok(await svc.create(data, created_by=user))


@router.patch("/{form_id}", response_model=APIResponse[FormOut])
async def update_form(
    form_id: uuid.UUID, data: FormUpdate, _: FormManager, svc: FormSvc
):
    return ok(await svc.update(form_id, data))

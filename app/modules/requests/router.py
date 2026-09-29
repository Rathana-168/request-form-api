import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_permission
from app.modules.requests.models import RequestStatus
from app.modules.requests.schemas import (
    RequestAction,
    RequestCreate,
    RequestListItem,
    RequestOut,
    RequestUpdate,
)
from app.modules.requests.service import RequestService
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams

router = APIRouter()


def get_request_service(db: DbSession) -> RequestService:
    return RequestService(db)


RequestSvc = Annotated[RequestService, Depends(get_request_service)]
Requester = Annotated[User, Depends(require_permission("request:create"))]


@router.get("", response_model=Page[RequestListItem])
async def list_my_requests(
    user: Requester,
    svc: RequestSvc,
    params: Annotated[PageParams, Depends()],
    status: RequestStatus | None = None,
    form_code: Annotated[str | None, Query(max_length=50)] = None,
):
    return await svc.list_mine(user, params, status=status, form_code=form_code)


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
async def create_draft(payload: RequestCreate, user: Requester, svc: RequestSvc):
    return await svc.create_draft(payload, user)


@router.get("/{request_id}", response_model=RequestOut)
async def get_request(request_id: uuid.UUID, user: Requester, svc: RequestSvc):
    return await svc.get_detail(request_id, user)


@router.patch("/{request_id}", response_model=RequestOut)
async def update_request(
    request_id: uuid.UUID, payload: RequestUpdate, user: Requester, svc: RequestSvc
):
    return await svc.update(request_id, payload, user)


@router.post("/{request_id}/submit", response_model=RequestOut)
async def submit_request(request_id: uuid.UUID, user: Requester, svc: RequestSvc):
    return await svc.submit(request_id, user)


@router.post("/{request_id}/cancel", response_model=RequestOut)
async def cancel_request(
    request_id: uuid.UUID, payload: RequestAction, user: Requester, svc: RequestSvc
):
    return await svc.cancel(request_id, user, payload.comment)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(request_id: uuid.UUID, user: Requester, svc: RequestSvc):
    await svc.delete_draft(request_id, user)
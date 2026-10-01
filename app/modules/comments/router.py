import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.modules.comments.schemas import CommentCreate, CommentOut, CommentUpdate
from app.modules.comments.service import CommentService
from app.shared.schemas import APIResponse, ok
from app.shared.schemas import Page, PageParams

router = APIRouter()


def get_comment_service(db: DbSession) -> CommentService:
    return CommentService(db)


CommentSvc = Annotated[CommentService, Depends(get_comment_service)]


@router.get("/{request_id}/comments", response_model=APIResponse[Page[CommentOut]])
async def list_comments(
    request_id: uuid.UUID, user: CurrentUser, svc: CommentSvc,
    params: Annotated[PageParams, Depends()],
):
    return ok(await svc.list(request_id, user, params))


@router.post(
    "/{request_id}/comments",
    response_model=APIResponse[CommentOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    request_id: uuid.UUID, body: CommentCreate, user: CurrentUser, svc: CommentSvc
):
    return ok(await svc.add(request_id, user, body.body))


@router.patch("/{request_id}/comments/{comment_id}", response_model=APIResponse[CommentOut])
async def edit_comment(
    request_id: uuid.UUID, comment_id: uuid.UUID, body: CommentUpdate,
    user: CurrentUser, svc: CommentSvc,
):
    return ok(await svc.edit(request_id, comment_id, user, body.body))


@router.delete("/{request_id}/comments/{comment_id}", response_model=APIResponse[None])
async def delete_comment(
    request_id: uuid.UUID, comment_id: uuid.UUID, user: CurrentUser, svc: CommentSvc
):
    await svc.delete(request_id, comment_id, user)
    return ok(None)


@router.get(
    "/{request_id}/comments/{comment_id}/replies",
    response_model=APIResponse[Page[CommentOut]],
)
async def list_replies(
    request_id: uuid.UUID, comment_id: uuid.UUID, user: CurrentUser, svc: CommentSvc,
    params: Annotated[PageParams, Depends()],
):
    return ok(await svc.list_replies(request_id, comment_id, user, params))


@router.post(
    "/{request_id}/comments/{comment_id}/replies",
    response_model=APIResponse[CommentOut],
    status_code=status.HTTP_201_CREATED,
)
async def reply_comment(
    request_id: uuid.UUID, comment_id: uuid.UUID, body: CommentCreate,
    user: CurrentUser, svc: CommentSvc,
):
    return ok(await svc.reply(request_id, comment_id, user, body.body))
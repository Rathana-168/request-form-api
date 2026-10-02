import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_permission
from app.modules.approvals.schemas import ApprovalAction, InboxItem
from app.modules.approvals.service import ApprovalService
from app.modules.requests.schemas import RequestOut
from app.modules.requests.service import RequestService
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams, ok, APIResponse

router = APIRouter()

Approver = Annotated[User, Depends(require_permission("approval:act"))]


def get_services(db: DbSession) -> tuple[ApprovalService, RequestService]:
    return ApprovalService(db), RequestService(db)


Services = Annotated[tuple[ApprovalService, RequestService], Depends(get_services)]


@router.get("/inbox", response_model=APIResponse[Page[InboxItem]])
async def inbox(
    user: Approver,
    svcs: Services,
    params: Annotated[PageParams, Depends()],
    form_code: Annotated[str | None, Query(max_length=50)] = None,
):
    return ok(await svcs[0].inbox(user, params, form_code))


@router.post("/{task_id}/approve", response_model=RequestOut)
async def approve(task_id: uuid.UUID, payload: ApprovalAction, user: Approver, svcs: Services):
    request = await svcs[0].approve(task_id, user, payload.comment)
    return await svcs[1].detail_for(request, user)


@router.post("/{task_id}/reject", response_model=RequestOut)
async def reject(task_id: uuid.UUID, payload: ApprovalAction, user: Approver, svcs: Services):
    request = await svcs[0].reject(task_id, user, payload.comment)
    return await svcs[1].detail_for(request, user)


@router.post("/{task_id}/return", response_model=RequestOut)
async def return_back(
    task_id: uuid.UUID, payload: ApprovalAction, user: Approver, svcs: Services
):
    request = await svcs[0].return_(task_id, user, payload.comment)
    return await svcs[1].detail_for(request, user)
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.api.deps import CurrentUser, DbSession
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import NotificationOut, UnreadCountOut
from app.modules.notifications.service import NotificationService
from app.shared.schemas import Page, PageParams, APIResponse, ok

router = APIRouter()


def get_notification_service(db: DbSession) -> NotificationService:
    return NotificationService(NotificationRepository(db))


NotificationSvc = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("", response_model=APIResponse[Page[NotificationOut]])
async def my_notifications(
    user: CurrentUser,
    svc: NotificationSvc,
    params: Annotated[PageParams, Depends()],
    unread_only: bool = False,
):
    return ok(await svc.list_mine(user, params, unread_only))


@router.get("/unread-count", response_model=APIResponse[UnreadCountOut])
async def unread_count(user: CurrentUser, svc: NotificationSvc):
    return ok(UnreadCountOut(count=await svc.unread_count(user)))


@router.post("/read", response_model=APIResponse[None])
async def mark_read(
    user: CurrentUser,
    svc: NotificationSvc,
    ids: Annotated[list[uuid.UUID] | None, Body(embed=True)] = None,
):
    await svc.mark_read(user, ids)
    return ok(None)
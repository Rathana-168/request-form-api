from enum import StrEnum
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forms.data import load_form_row
from app.modules.forms.plugin import FormContext
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.requests.models import Request
from app.modules.users.models import User
from app.workflow.enums import WorkflowEvent


# event -> FormHooks method name
HOOKS = {
    WorkflowEvent.SUBMITTED: "on_submit",
    WorkflowEvent.STEP_APPROVED: "on_step_approved",
    WorkflowEvent.STEP_REJECTED: "on_step_rejected",
    WorkflowEvent.APPROVED: "on_approved",
    WorkflowEvent.REJECTED: "on_rejected",
    WorkflowEvent.RETURNED: "on_returned",
    WorkflowEvent.CANCELLED: "on_cancelled",
}


async def dispatch(
    db: AsyncSession, event: WorkflowEvent, request: Request, actor: User,
    *, step: dict[str, Any] | None = None,
    user_ids: list[uuid.UUID] | None = None,   # NEW: approvers, for assigned / cancelled
    comment: str | None = None,                # NEW: for rejected / returned
) -> None:
    # 1. Plugin hook (unchanged, but skip events without one)
    if hook_name := HOOKS.get(event):
        definition, row = await load_form_row(db, request)
        ctx = FormContext(db=db, request=request, user=actor, definition=definition)
        hook = getattr(definition.hooks, hook_name)
        await (hook(ctx, row, step) if step is not None else hook(ctx, row))

    # 2. Notifications
    recipients = user_ids if user_ids is not None else [request.requester_id]
    NotificationService(NotificationRepository(db)).create_for_event(
        event, request, actor, recipients, step=step, comment=comment
    )

    # Later: rules
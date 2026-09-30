from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forms.plugin import FormContext
from app.modules.forms.registry import get_definition
from app.modules.requests.models import Request
from app.modules.users.models import User


class Event(StrEnum):
    SUBMITTED = "submitted"
    STEP_APPROVED = "step_approved"
    STEP_REJECTED = "step_rejected"
    APPROVED = "approved"      # all steps done
    REJECTED = "rejected"
    RETURNED = "returned"
    CANCELLED = "cancelled"


# event -> FormHooks method name
HOOKS = {
    Event.SUBMITTED: "on_submit",
    Event.STEP_APPROVED: "on_step_approved",
    Event.STEP_REJECTED: "on_step_rejected",
    Event.APPROVED: "on_approved",
    Event.REJECTED: "on_rejected",
    Event.RETURNED: "on_returned",
    Event.CANCELLED: "on_cancelled",
}


async def dispatch(
    db: AsyncSession, event: Event, request: Request, actor: User,
    *, step: dict[str, Any] | None = None, data: Any = None,
) -> None:
    """Single exit point for workflow events. Today: plugin hooks. Later: rules too."""
    definition = get_definition(request.form_code)
    if data is None:
        data = await db.scalar(
            select(definition.model).where(definition.model.request_id == request.id)
        )
    ctx = FormContext(db=db, request=request, user=actor, definition=definition)

    hook = getattr(definition.hooks, HOOKS[event])
    if event in (Event.STEP_APPROVED, Event.STEP_REJECTED):
        await hook(ctx, data, step)
    else:
        await hook(ctx, data)

    # Later: await rules.run(db, event, request, actor, step=step, data=data)
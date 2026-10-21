import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.events.models import OutboxEvent
from app.modules.requests.models import Request
from app.modules.users.models import User
from app.workflow.enums import WorkflowEvent


def _contact(u: User) -> dict[str, Any]:
    return {"id": str(u.id), "name": u.full_name, "email": u.email}


def build_event(
    event: WorkflowEvent, request: Request, actor: User | None, *,
    recipients: list[User],
    step: dict[str, Any] | None = None,
    comment: str | None = None,
    extra: dict[str, str] | None = None,
    event_id: uuid.UUID | None = None,
) -> OutboxEvent:
    event_id = event_id or uuid.uuid4()
    return OutboxEvent(
        id=event_id,
        topic=get_settings().KAFKA_WORKFLOW_TOPIC,
        key=str(request.id),
        event_type=event.value,
        payload={
            "event_id": str(event_id),
            "event_type": event.value,
            "version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "request": {
                "id": str(request.id),
                "request_no": request.request_no,
                "form_code": request.form.code,
                "form_name": request.form.name,
                "status": request.status.value,
                "requester_id": str(request.requester_id),
            },
            "actor_id": str(actor.id) if actor else None,   # None = system
            "actor_name": actor.full_name if actor else None,
            "step": {"step_no": step["step_no"], "name": step["name"]} if step else None,
            "recipient_ids": [str(u.id) for u in recipients],
            "recipients": [_contact(u) for u in recipients],
            "comment": comment,
            "extra": extra or {},
        },
    )
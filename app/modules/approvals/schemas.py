import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.approvals.models import TaskStatus
from app.modules.requests.models import RequestStatus
from app.shared.schemas import ORMModel


class ApprovalAction(BaseModel):
    comment: str | None = Field(None, max_length=2000)


class UserBrief(ORMModel):
    id: uuid.UUID
    full_name: str


class TaskOut(ORMModel):
    id: uuid.UUID
    request_id: uuid.UUID
    step_no: int
    assignee: UserBrief
    status: TaskStatus
    comment: str | None
    acted_at: datetime | None
    created_at: datetime


class RequestBrief(ORMModel):
    id: uuid.UUID
    request_no: str | None
    form_code: str
    status: RequestStatus
    requester: UserBrief
    submitted_at: datetime | None
    stage: str


class InboxItem(ORMModel):
    """A pending task with enough of the request to show in a list."""

    id: uuid.UUID
    step_no: int
    step_name: str
    created_at: datetime
    request: RequestBrief
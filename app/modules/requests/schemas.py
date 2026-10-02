import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.attachments.schemas import AttachmentOut
from app.modules.requests.models import HistoryAction, RequestStatus
from app.modules.users.schemas import UserBrief
from app.shared.schemas import ORMModel


class RequestCreate(BaseModel):
    form_code: str
    attachments: list[uuid.UUID] = []
    data: dict[str, Any]  # validated against the form plugin's create_schema


class RequestUpdate(BaseModel):
    attachments: list[uuid.UUID] = []
    data: dict[str, Any]  # partial; validated against the plugin's update_schema


class RequestAction(BaseModel):
    comment: str | None = Field(None, max_length=2000)


class HistoryOut(ORMModel):
    id: uuid.UUID
    action: HistoryAction
    actor: UserBrief | None
    step_no: int | None
    comment: str | None
    data_snapshot: dict[str, Any] | None
    created_at: datetime


class RequestListItem(ORMModel):
    id: uuid.UUID
    request_no: str | None
    form_code: str
    status: RequestStatus
    requester: UserBrief
    current_step: int | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    stage: str  # workflow's display status: submitted, reviewed, done...


class ActionOut(BaseModel):
    key: str  # edit | submit | delete | cancel | approve | return | reject
    label: str
    task_id: uuid.UUID | None  # set for approver actions: POST /approvals/{task_id}/{key}
    require_comment: bool


class ApprovalStepOut(BaseModel):
    order: int
    label: str


class RequestOut(RequestListItem):
    attachments: list[AttachmentOut] = []
    completed_at: datetime | None
    data: dict[str, Any]  # shaped by the plugin's read_schema
    history: list[HistoryOut]
    approvals: list[ApprovalOut]
    available_actions: list[ActionOut]  # for the current user
    approval_steps: list[ApprovalStepOut] = []
    comment_count: int = 0


class ApprovalOut(ORMModel):
    id: uuid.UUID
    step_no: int
    assignee: UserBrief
    status: str
    comment: str | None
    acted_at: datetime | None
    remind_at: datetime | None
    escalate_at: datetime | None
    escalated_at: datetime | None

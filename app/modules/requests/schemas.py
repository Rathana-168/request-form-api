import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.requests.models import HistoryAction, RequestStatus
from app.shared.schemas import ORMModel


class RequestCreate(BaseModel):
    form_code: str
    data: dict[str, Any]  # validated against the form plugin's create_schema


class RequestUpdate(BaseModel):
    data: dict[str, Any]  # partial; validated against the plugin's update_schema


class RequestAction(BaseModel):
    comment: str | None = Field(None, max_length=2000)


class UserBrief(ORMModel):
    id: uuid.UUID
    full_name: str


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


class RequestOut(RequestListItem):
    completed_at: datetime | None
    data: dict[str, Any]  # shaped by the plugin's read_schema
    history: list[HistoryOut]
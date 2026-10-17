import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.shared.schemas import ORMModel
from app.workflow.enums import WorkflowEvent
from app.workflow.schemas import Conditions


class ActionIn(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    params: dict[str, Any] = {}


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    event: WorkflowEvent
    step_no: int | None = Field(None, ge=1)
    conditions: Conditions | None = None
    actions: list[ActionIn] = Field(min_length=1)
    priority: int = Field(100, ge=0, le=10_000)
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    event: WorkflowEvent | None = None
    step_no: int | None = Field(None, ge=1)
    conditions: Conditions | None = None
    actions: list[ActionIn] | None = Field(None, min_length=1)
    priority: int | None = Field(None, ge=0, le=10_000)
    is_active: bool | None = None


class RuleOut(ORMModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    event: str
    step_no: int | None
    conditions: list[Any] | dict[str, Any] | None
    actions: list[dict[str, Any]]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ActionTypeOut(BaseModel):
    type: str
    description: str
    is_async: bool
    params_schema: dict[str, Any]


class RuleTestIn(BaseModel):
    request_id: uuid.UUID
    rule: RuleCreate


class ActionPreview(BaseModel):
    type: str
    params: dict[str, Any]
    valid: bool
    error: str | None = None


class RuleTestOut(BaseModel):
    matched: bool
    actions: list[ActionPreview] = []
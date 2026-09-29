import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.schemas import ORMModel
from app.workflow.models import ApprovalMode, AssigneeType

Op = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"]


class Condition(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    op: Op
    value: Any

    @model_validator(mode="after")
    def list_for_in(self):
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"'{self.op}' needs a list value")
        return self


class StepIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    assignee_type: AssigneeType
    assignee_user_id: uuid.UUID | None = None
    assignee_role_id: uuid.UUID | None = None
    mode: ApprovalMode = ApprovalMode.ANY
    conditions: list[Condition] | None = None
    skip_if_requester: bool = True

    @model_validator(mode="after")
    def check_assignee(self):
        if self.assignee_type is AssigneeType.USER and not self.assignee_user_id:
            raise ValueError("assignee_user_id is required for type 'user'")
        if self.assignee_type is AssigneeType.ROLE and not self.assignee_role_id:
            raise ValueError("assignee_role_id is required for type 'role'")
        return self


class WorkflowCreate(BaseModel):
    form_code: str
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    steps: list[StepIn] = Field(min_length=1)  # order = step_no


class WorkflowUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    steps: list[StepIn] = Field(min_length=1)  # replaces all steps


class StepOut(ORMModel):
    step_no: int
    name: str
    assignee_type: AssigneeType
    assignee_user_id: uuid.UUID | None
    assignee_role_id: uuid.UUID | None
    mode: ApprovalMode
    conditions: list[dict[str, Any]] | None
    skip_if_requester: bool


class WorkflowOut(ORMModel):
    id: uuid.UUID
    form_code: str
    name: str
    description: str | None
    is_active: bool
    steps: list[StepOut]
    created_at: datetime
    updated_at: datetime
import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.schemas import ORMModel
from app.workflow.enums import EscalationAction
from app.workflow.models import ApprovalMode, AssigneeType

Op = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"]
Action = Literal["reject", "return"]
STATUS_PATTERN = r"^[a-z][a-z0-9_]{0,49}$"   # stage names like "submitted", "hr_review"


class Condition(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    op: Op
    value: Any

    @model_validator(mode="after")
    def list_for_in(self):
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"'{self.op}' needs a list value")
        return self


class ConditionGroup(BaseModel):
    """{"all": [...]} or {"any": [...]}; items are rules or nested groups."""

    model_config = ConfigDict(populate_by_name=True)

    all_: list[Condition | ConditionGroup] | None = Field(None, alias="all", min_length=1)
    any_: list[Condition | ConditionGroup] | None = Field(None, alias="any", min_length=1)

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.all_ is None) == (self.any_ is None):
            raise ValueError("A condition group needs exactly one of 'all' or 'any'")
        return self


Conditions = list[Condition | ConditionGroup] | ConditionGroup


class StepIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    status: str = Field(pattern=STATUS_PATTERN, examples=["submitted"])
    action_label: str = Field("Approve", min_length=1, max_length=50)

    assignee_type: AssigneeType
    assignee_user_id: uuid.UUID | None = None
    assignee_role_id: uuid.UUID | None = None
    assignee_field: str | None = Field(None, max_length=100)
    mode: ApprovalMode = ApprovalMode.ANY
    skip_if_requester: bool = True

    conditions: Conditions | None = None

    allow_reject: bool = True
    allow_return: bool = True
    return_to: str = Field("requester", pattern=r"^(requester|previous|[1-9][0-9]*)$")
    require_comment_on: list[Action] = []

    @model_validator(mode="after")
    def check_assignee(self):
        needs = {
            AssigneeType.USER: ("assignee_user_id", self.assignee_user_id),
            AssigneeType.ROLE: ("assignee_role_id", self.assignee_role_id),
            AssigneeType.FORM_FIELD: ("assignee_field", self.assignee_field),
        }
        if self.assignee_type in needs and not needs[self.assignee_type][1]:
            field, _ = needs[self.assignee_type]
            raise ValueError(f"{field} is required for type '{self.assignee_type}'")
        return self

    def conditions_json(self) -> list[Any] | dict[str, Any] | None:
        """Plain JSON to store in the DB (aliases 'all'/'any', no nulls)."""
        if self.conditions is None:
            return None
        if isinstance(self.conditions, list):
            return [c.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for c in self.conditions]
        return self.conditions.model_dump(mode="json", by_alias=True, exclude_none=True)


class WorkflowCreate(BaseModel):
    form_code: str
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    steps: list[StepIn] = Field(min_length=1)  # order = step_no
    completed_status: str = Field("approved", pattern=STATUS_PATTERN)


class WorkflowUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    steps: list[StepIn] = Field(min_length=1)  # replaces all steps
    completed_status: str = Field("approved", pattern=STATUS_PATTERN)


class StepOut(ORMModel):
    step_no: int
    name: str
    status: str
    action_label: str
    assignee_type: AssigneeType
    assignee_user_id: uuid.UUID | None
    assignee_role_id: uuid.UUID | None
    assignee_field: str | None
    mode: ApprovalMode
    skip_if_requester: bool
    conditions: list[Any] | dict[str, Any] | None
    allow_reject: bool
    allow_return: bool
    return_to: str
    require_comment_on: list[str]
    remind_after_hours: int | None = Field(None, ge=1)
    escalate_after_hours: int | None = Field(None, ge=1)
    escalation_action: EscalationAction = EscalationAction.NOTIFY_MANAGER

    @model_validator(mode="after")
    def check_sla(self) -> Self:
        r, e = self.remind_after_hours, self.escalate_after_hours
        if r and e and e <= r:
            raise ValueError("escalate_after_hours must be greater than remind_after_hours")
        return self


class WorkflowOut(ORMModel):
    id: uuid.UUID
    form_code: str
    name: str
    description: str | None
    completed_status: str
    is_active: bool
    steps: list[StepOut]
    created_at: datetime
    updated_at: datetime
    
    
class AssigneeTypeOut(BaseModel):
    value: AssigneeType
    label: str
    description: str
    needs: Literal["user", "role", "field"] | None  # extra input the step requires
    supported: bool  # False = resolvers.py can't find an approver for it yet
    
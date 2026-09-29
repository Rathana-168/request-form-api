import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.types import str_enum


class AssigneeType(StrEnum):
    USER = "user"  # one specific user (assignee_user_id)
    ROLE = "role"  # every active user with the role (assignee_role_id)
    REQUESTER_MANAGER = "requester_manager"  # requester.manager_id
    DEPARTMENT_HEAD = "department_head"  # requester.department.head_id
    FORM_FIELD = "form_field"


class ApprovalMode(StrEnum):
    ANY = "any"  # first approval completes the step
    ALL = "all"  # every assigned approver must approve


class Workflow(UUIDMixin, TimestampMixin, Base):
    """Approval route for one form. Only one active workflow per form."""

    __tablename__ = "workflows"
    __table_args__ = (
        Index(
            "uq_workflows_one_active_per_form",
            "form_code",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    form_code: Mapped[str] = mapped_column(
        ForeignKey("forms.code", ondelete="RESTRICT", onupdate="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="WorkflowStep.step_no"
    )
    completed_status: Mapped[str] = mapped_column(
        String(50), default="approved", server_default="approved"
    )


class WorkflowStep(UUIDMixin, Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (UniqueConstraint("workflow_id", "step_no"),)

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    step_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(150))

    assignee_type: Mapped[AssigneeType] = mapped_column(str_enum(AssigneeType))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    assignee_role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT")
    )
    assignee_field: Mapped[str | None] = mapped_column(String(100))
    mode: Mapped[ApprovalMode] = mapped_column(str_enum(ApprovalMode), default=ApprovalMode.ANY)

    # [{"field": "days", "op": "gt", "value": 3}, ...] - all must match (AND). Null = always.
    conditions: Mapped[list[dict[str, Any]] | dict[str, Any] | None] = mapped_column(JSONB)
    skip_if_requester: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(50), server_default="in_review")
    action_label: Mapped[str] = mapped_column(String(50), default="Approve", server_default="Approve")

    allow_reject: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    allow_return: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    return_to: Mapped[str] = mapped_column(String(20), default="requester", server_default="requester")
    require_comment_on: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
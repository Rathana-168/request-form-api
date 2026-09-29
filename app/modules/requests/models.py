import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.types import str_enum
from app.modules.forms.models import Form
from app.modules.users.models import User


class RequestStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    RETURNED = "returned"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


EDITABLE_STATUSES = {RequestStatus.DRAFT, RequestStatus.RETURNED}
FINAL_STATUSES = {
    RequestStatus.APPROVED,
    RequestStatus.REJECTED,
    RequestStatus.CANCELLED,
}


class HistoryAction(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    RESUBMITTED = "resubmitted"
    APPROVED = "approved"  # one step approved
    SKIPPED = "skipped"  # step skipped (condition false / requester is the approver)
    REJECTED = "rejected"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    COMPLETED = "completed"  # all steps approved


class Request(UUIDMixin, TimestampMixin, Base):
    """Shared by every form. The form's own fields live in the plugin's table."""

    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_requester_status", "requester_id", "status"),
        Index("ix_requests_form_status", "form_code", "status"),
    )

    request_no: Mapped[str | None] = mapped_column(String(30), unique=True)
    form_code: Mapped[str] = mapped_column(
        ForeignKey("forms.code", ondelete="RESTRICT", onupdate="CASCADE")
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[RequestStatus] = mapped_column(
        str_enum(RequestStatus), default=RequestStatus.DRAFT
    )

    # Workflow state
    # workflow_id: Mapped[uuid.UUID | None] = mapped_column(
    #     ForeignKey("workflows.id", ondelete="SET NULL")
    # )
    workflow_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    current_step: Mapped[int | None] = mapped_column(Integer)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requester: Mapped[User] = relationship(foreign_keys=[requester_id], lazy="selectin")
    form: Mapped[Form] = relationship(
        primaryjoin="Request.form_code == Form.code",
        foreign_keys=[form_code],
        lazy="selectin",
    )


class RequestHistory(UUIDMixin, Base):
    """Timeline of a request. Each submit stores a snapshot of the form data."""

    __tablename__ = "request_history"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[HistoryAction] = mapped_column(str_enum(HistoryAction))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    step_no: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    data_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id], lazy="selectin")


class RequestCounter(Base):
    """Per-prefix-per-year counter for readable numbers: LEAVE-2026-00001."""

    __tablename__ = "request_counters"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)  # "LEAVE-2026"
    value: Mapped[int] = mapped_column(Integer, default=0)

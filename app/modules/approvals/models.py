import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.types import str_enum
from app.modules.users.models import User


class TaskStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    CLOSED = "closed"  # no longer needed: another approver acted, or the request ended


class ApprovalTask(UUIDMixin, TimestampMixin, Base):
    """One approver's to-do for one step of one request."""

    __tablename__ = "approval_tasks"
    __table_args__ = (
        Index("ix_approval_tasks_assignee_status", "assignee_id", "status"),
        Index("ix_approval_tasks_request_step", "request_id", "step_no"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    step_no: Mapped[int] = mapped_column(Integer)
    assignee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[TaskStatus] = mapped_column(str_enum(TaskStatus), default=TaskStatus.PENDING)
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id], lazy="selectin")
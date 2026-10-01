import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
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
    REASSIGNED = "reassigned"


class ApprovalTask(UUIDMixin, TimestampMixin, Base):
    """One approver's to-do for one step of one request."""

    __tablename__ = "approval_tasks"
    __table_args__ = (
        Index("ix_approval_tasks_assignee_status", "assignee_id", "status"),
        Index("ix_approval_tasks_request_step", "request_id", "step_no"),
        Index(
        "ix_approval_tasks_pending_sla", "remind_at", "escalate_at",
            postgresql_where=text("status = 'pending'"),
        ),
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
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    acted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    acted_by: Mapped[User | None] = relationship(foreign_keys=[acted_by_id], lazy="selectin")


class ApprovalProxy(UUIDMixin, TimestampMixin, Base):
    """B (proxy) may act on A's (principal) approval tasks during [start_at, end_at)."""

    __tablename__ = "approval_proxies"
    __table_args__ = (
        CheckConstraint("principal_id <> proxy_id", name="not_self"),
        CheckConstraint("end_at > start_at", name="valid_period"),
        Index(
            "ix_approval_proxies_proxy_active", "proxy_id", "start_at", "end_at",
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_approval_proxies_principal_active", "principal_id", "start_at", "end_at",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    proxy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ended early
    source_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL")  # the Proxy Request that created it
    )

    principal: Mapped[User] = relationship(foreign_keys=[principal_id], lazy="selectin")
    proxy: Mapped[User] = relationship(foreign_keys=[proxy_id], lazy="selectin")
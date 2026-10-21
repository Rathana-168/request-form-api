import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.types import str_enum
from app.rules.enums import ExecutionStatus


class WorkflowRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_rules"

    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    event: Mapped[str] = mapped_column(String(50))
    step_no: Mapped[int | None] = mapped_column(Integer)
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    actions: Mapped[list] = mapped_column(JSONB)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    __table_args__ = (
        Index("ix_workflow_rules_lookup", "workflow_id", "event",
              postgresql_where=text("is_active")),
    )


class RuleExecution(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rule_executions"

    event_id: Mapped[uuid.UUID]
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    rule_id: Mapped[uuid.UUID]
    rule_name: Mapped[str] = mapped_column(String(150))
    action_index: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSONB)          # already rendered
    is_async: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[ExecutionStatus] = mapped_column(str_enum(ExecutionStatus))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("event_id", "rule_id", "action_index"),
        Index("ix_rule_executions_pending", "next_attempt_at",
              postgresql_where=text("status = 'pending' AND is_async")),
        Index("ix_rule_executions_request", "request_id"),
    )
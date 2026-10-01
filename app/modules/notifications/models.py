import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.db.types import str_enum


class NotificationType(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETURNED = "returned"
    CANCELLED = "cancelled"

    TASK_REMINDER = "task_reminder"
    TASK_ESCALATED = "task_escalated"
    TASK_REASSIGNED = "task_reassigned"


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(str_enum(NotificationType))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
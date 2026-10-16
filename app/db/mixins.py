import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class AuditMixin:
    """Who created / last changed the row. Filled automatically (see db/audit.py)."""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HrSyncedMixin:
    """Columns for tables mirrored from HR. Matched by hr_code, never deleted."""
    hr_code: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
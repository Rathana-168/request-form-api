from datetime import date

from sqlalchemy import CheckConstraint, Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum
from app.modules.forms.definitions.leave_request.constants import LeaveType
from app.modules.forms.plugin import FormDataMixin


class LeaveRequestData(FormDataMixin, Base):
    __tablename__ = "form_leave_requests"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="date_range"),)

    leave_type: Mapped[LeaveType] = mapped_column(str_enum(LeaveType))
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Numeric(5, 1))
    reason: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(String(100))
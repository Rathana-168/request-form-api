import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.forms.plugin import FormDataMixin
from app.modules.users.models import User


class ProxyRequestData(FormDataMixin, Base):
    __tablename__ = "proxy_requests"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="valid_period"),)

    proxy_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)  # inclusive
    reason: Mapped[str] = mapped_column(Text)

    proxy_user: Mapped[User] = relationship(foreign_keys=[proxy_user_id], lazy="selectin")
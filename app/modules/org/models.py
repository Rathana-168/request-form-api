import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import HrSyncedMixin


class Department(HrSyncedMixin, Base):
    __tablename__ = "department"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    department_name: Mapped[str] = mapped_column(String(200))
    department_abbr: Mapped[str | None] = mapped_column(String(200))
    department_cost_center: Mapped[str | None] = mapped_column(String(200))
    
    
class Position(HrSyncedMixin, Base):
    __tablename__ = "positions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    department_name: Mapped[str] = mapped_column(String(200))
    department_abbr: Mapped[str | None] = mapped_column(String(200))
    department_cost_center: Mapped[str | None] = mapped_column(String(200))
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Permission(UUIDMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True)  # e.g. "form:create"
    description: Mapped[str | None] = mapped_column(String(255))


class Role(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, lazy="raise"
    )


class Department(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    head_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True)
    )

    parent: Mapped[Department | None] = relationship(remote_side="Department.id")
    head: Mapped[User | None] = relationship(foreign_keys=[head_id])


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    staff_id: Mapped[str | None] = mapped_column(String(10), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), deferred=True)
    full_name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    department: Mapped[Department | None] = relationship(
        foreign_keys=[department_id], lazy="joined"
    )
    manager: Mapped[User | None] = relationship(remote_side="User.id")
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="raise")

    profile: Mapped[EmployeeProfile | None] = relationship(
        back_populates="user", uselist=False, lazy="raise"
    )
    
    @property
    def permission_codes(self) -> set[str]:
        return {p.code for role in self.roles for p in role.permissions}


class EmployeeProfile(Base):
    """HR data, read-only in the app. Only the org sync (and seed) writes it."""
    __tablename__ = "employee_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name_en: Mapped[str] = mapped_column(String(200))
    full_name_kh: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(150))
    branch: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    work_email: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(10))
    date_of_birth: Mapped[date | None]
    hire_date: Mapped[date | None]
    employment_status: Mapped[str | None] = mapped_column(String(30))
    hr_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="profile")
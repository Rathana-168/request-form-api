import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.shared.schemas import ORMModel


# ---- Nested outputs ----
class RoleBrief(ORMModel):
    id: uuid.UUID
    name: str


class DepartmentBrief(ORMModel):
    id: uuid.UUID
    name: str
    code: str


# ---- User ----
class UserCreate(BaseModel):
    email: EmailStr
    staff_id: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=150)
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    staff_id: str
    full_name: str | None = Field(None, min_length=1, max_length=150)
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


class UserOut(ORMModel):
    id: uuid.UUID
    staff_id: str
    email: EmailStr
    full_name: str
    is_active: bool
    department: DepartmentBrief | None
    manager_id: uuid.UUID | None
    roles: list[RoleBrief]
    created_at: datetime


class UserBrief(ORMModel):
    id: uuid.UUID
    full_name: str
    staff_id: str
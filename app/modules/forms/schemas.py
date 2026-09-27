import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.schemas import ORMModel


class FormCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,49}$", examples=["LEAVE_REQUEST"])
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    category: str | None = Field(None, max_length=50)


class FormUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    category: str | None = Field(None, max_length=50)
    is_active: bool | None = None


class FormOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: str | None
    is_active: bool
    created_at: datetime

import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.modules.users.schemas import UserBrief
from app.shared.schemas import ORMModel


class ProxyRequestCreate(BaseModel):
    proxy_user_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ProxyRequestUpdate(BaseModel):
    proxy_user_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(None, min_length=1, max_length=500)


class ProxyRequestOut(ORMModel):
    proxy_user_id: uuid.UUID
    proxy_user: UserBrief
    start_date: date
    end_date: date
    reason: str


class ProxyOut(ORMModel):
    """An active (or scheduled) proxy, for the 'my proxies' endpoint."""
    id: uuid.UUID
    principal: UserBrief
    proxy: UserBrief
    start_at: datetime
    end_at: datetime
    ended_at: datetime | None
    source_request_id: uuid.UUID | None
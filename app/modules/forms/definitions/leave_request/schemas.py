import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.modules.forms.definitions.leave_request.constants import LeaveType
from app.shared.schemas import ORMModel


class LeaveCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    days: float = Field(gt=0, le=365, multiple_of=0.5)
    reason: str | None = Field(None, max_length=1000)
    contact: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveUpdate(BaseModel):
    leave_type: LeaveType | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: float | None = Field(None, gt=0, le=365, multiple_of=0.5)
    reason: str | None = Field(None, max_length=1000)
    contact: str | None = Field(None, max_length=100)


class LeaveOut(ORMModel):
    id: uuid.UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    days: float
    reason: str | None
    contact: str | None
from datetime import datetime
import uuid

from pydantic import BaseModel

from app.modules.notifications.models import NotificationType
from app.shared.schemas import ORMModel


class NotificationOut(ORMModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    body: str | None
    request_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
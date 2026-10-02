import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.users.schemas import UserBrief
from app.shared.schemas import ORMModel


class AttachmentOut(ORMModel):
    id: uuid.UUID
    file_name: str
    content_type: str
    size: int
    uploaded_by: UserBrief | None
    created_at: datetime


class DownloadOut(BaseModel):
    url: str
    expires_in: int
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.attachments.schemas import AttachmentOut
from app.modules.users.schemas import UserBrief


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    attachments: list[uuid.UUID] = Field(default=[], max_length=5)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: uuid.UUID
    body: str | None            # None when deleted
    author: UserBrief | None
    on_behalf_of: UserBrief | None
    created_at: datetime
    edited_at: datetime | None
    is_deleted: bool
    can_edit: bool
    parent_id: uuid.UUID | None = None
    reply_count: int = 0
    last_reply_at: datetime | None = None
    attachments: list[AttachmentOut] = []
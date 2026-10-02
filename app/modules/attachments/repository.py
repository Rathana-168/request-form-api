import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attachments.models import Attachment


class AttachmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add_many(self, items: list[Attachment]) -> None:
        self.db.add_all(items)

    async def get(self, attachment_id: uuid.UUID) -> Attachment | None:
        return await self.db.get(Attachment, attachment_id)

    async def get_registered_attachments(self, ids: list[uuid.UUID], owner_id: uuid.UUID) -> list[Attachment]:
        attachments = await self.db.scalars(
            select(Attachment)
            .where(Attachment.id.in_(ids))
            .where(Attachment.uploaded_by_id == owner_id)
            .where(Attachment.request_id.is_(None))
        )
        return list(attachments)

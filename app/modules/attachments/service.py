import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.file_service.client import FileRejectedError
from app.integrations.registry import file_service
from app.modules.attachments.exceptions import (
    AttachmentNotFoundError, FileTooLargeError, InvalidUploadError,
)
from app.modules.attachments.models import Attachment
from app.modules.attachments.schemas import DownloadOut
from app.modules.requests.access import can_view_request
from app.modules.requests.models import Request
from app.modules.users.models import User


class AttachmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload(self, upload: UploadFile, user: User) -> Attachment:
        max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
        if upload.size is not None and upload.size > max_bytes:
            raise FileTooLargeError(get_settings().MAX_UPLOAD_MB)
        try:
            info = await file_service.upload(
                upload.file,
                upload.filename or "file",
                upload.content_type or "application/octet-stream",
                uploaded_by=str(user.id),
            )
        except FileRejectedError as exc:
            raise InvalidUploadError(str(exc)) from exc

        att = Attachment(file_name=info.file_name, content_type=info.content_type,
            size=info.size, uploaded_by=user,
        )
        self.db.add(att)
        await self.db.flush()
        return att

    async def download(self, attachment_id: uuid.UUID, user: User) -> DownloadOut:
        att = await self.db.get(Attachment, attachment_id)
        if att is None or not await self._can_view(att, user):
            raise AttachmentNotFoundError()   # same error, so IDs can't be probed
        url, expires_in = await file_service.download_url(att.id)
        return DownloadOut(url=url, expires_in=expires_in)

    async def _can_view(self, att: Attachment, user: User) -> bool:
        if att.request_id is None:                     # not used yet: only the uploader
            return att.uploaded_by_id == user.id
        request = await self.db.get(Request, att.request_id)
        return request is not None and await can_view_request(self.db, request, user)

    # async def claim(
    #     self, request: Request, ids: set[uuid.UUID], user: User, *, used_in: str = "form"
    # ) -> dict[uuid.UUID, Attachment]:
        # rows: dict[uuid.UUID, Attachment] = {}
        # if ids:
        #     result = await self.db.scalars(
        #         select(Attachment).where(Attachment.id.in_(ids)).with_for_update()
        #     )
        #     rows = {a.id: a for a in result}
        # for file_id in ids:
        #     att = rows.get(file_id)
        #     mine_unused = att is not None and att.request_id is None and att.uploaded_by_id == user.id
        #     already_here = att is not None and att.request_id == request.id
        #     if not (mine_unused or already_here):
        #         raise InvalidAttachmentError(file_id)
        #     att.request_id, att.used_in = request.id, used_in

        # # files this form used before but no longer references -> unclaimed (cleanup removes later)
        # stmt = update(Attachment).where(
        #     Attachment.request_id == request.id, Attachment.used_in == used_in
        # )
        # if ids:
        #     stmt = stmt.where(Attachment.id.not_in(ids))
        # await self.db.execute(stmt.values(request_id=None, used_in=None))
        # return rows
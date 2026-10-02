import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.modules.attachments.schemas import AttachmentOut, DownloadOut
from app.modules.attachments.service import AttachmentService
from app.shared.schemas import APIResponse, ok

router = APIRouter()


def get_attachment_service(db: DbSession) -> AttachmentService:
    return AttachmentService(db)


AttachmentSvc = Annotated[AttachmentService, Depends(get_attachment_service)]


@router.post("", response_model=APIResponse[AttachmentOut], status_code=status.HTTP_201_CREATED)
async def upload_file(user: CurrentUser, svc: AttachmentSvc, file: UploadFile = File(...)):
    return ok(await svc.upload(file, user))


@router.get("/{attachment_id}/download", response_model=APIResponse[DownloadOut])
async def download_file(attachment_id: uuid.UUID, user: CurrentUser, svc: AttachmentSvc):
    return ok(await svc.download(attachment_id, user))
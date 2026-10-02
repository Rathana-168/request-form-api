from typing import BinaryIO
import uuid

from app.integrations.base import BaseServiceClient
from app.integrations.file_service.schemas import FileInfo


class FileRejectedError(Exception):
    """The file service refused the file (too large, type not allowed, …)."""


class FileServiceClient(BaseServiceClient):
    name = "file-service"

    async def upload(self, file: BinaryIO, file_name: str, content_type: str, uploaded_by: str) -> FileInfo:
        resp = await self.request(
            "POST", "/files",
            files={"file": (file_name, file, content_type)},
            headers={"X-Uploaded-By": uploaded_by},
            timeout=60.0,                          # uploads take longer than normal calls
        )
        if resp.status_code >= 400:
            raise FileRejectedError(resp.json().get("message", "File rejected"))
        return FileInfo.model_validate(self.data(resp))

    async def download_url(self, file_id: uuid.UUID) -> tuple[str, int]:
        d = self.data(await self.request("POST", f"/files/{file_id}/download-url"))
        return d["url"], d["expires_in"]

    async def delete(self, file_id: uuid.UUID) -> None:     # used by cleanup in Step 3
        await self.request("DELETE", f"/files/{file_id}")
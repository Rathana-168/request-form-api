import uuid

from pydantic import BaseModel


class FileInfo(BaseModel):
    """The file service's file metadata. Match the fields to your service."""
    id: str
    file_name: str
    content_type: str
    size: int
    uploaded_by: str


class FileInfo(BaseModel):
    id: uuid.UUID
    file_name: str
    content_type: str
    size: int
    
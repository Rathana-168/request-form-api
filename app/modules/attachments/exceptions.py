import uuid

from pydantic import ValidationError

from app.core.exceptions import NotFoundError


class AttachmentNotFoundError(NotFoundError):
    code = "ATTACHMENT_NOT_FOUND"

    def __init__(self, message: str = "Attachment not found"):
        super().__init__(message)


class FileTooLargeError(ValidationError):
    code = "FILE_TOO_LARGE"

    def __init__(self, max_mb: int):
        super().__init__(f"File is larger than {max_mb} MB")


class InvalidUploadError(ValidationError):
    code = "INVALID_UPLOAD"


class InvalidAttachmentError(ValidationError):
    code = "INVALID_ATTACHMENT"

    def __init__(self, file_id: uuid.UUID):
        super().__init__(f"Attachment {file_id} not found, not yours, or used elsewhere")
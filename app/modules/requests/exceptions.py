from fastapi import status

from app.core.exceptions import AppException, NotFoundError, PermissionDeniedError


class RequestNotFoundError(NotFoundError):
    code = "REQUEST_NOT_FOUND"

    def __init__(self):
        super().__init__("Request not found")


class NotRequesterError(PermissionDeniedError):
    code = "NOT_REQUESTER"

    def __init__(self):
        super().__init__("Only the requester can do this")


class InvalidRequestStatusError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_REQUEST_STATUS"

    def __init__(self, action: str, current: str):
        super().__init__(f"Cannot {action} a request in status '{current}'")
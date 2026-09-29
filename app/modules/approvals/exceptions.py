from fastapi import status

from app.core.exceptions import AppException, NotFoundError


class TaskNotFoundError(NotFoundError):
    code = "TASK_NOT_FOUND"

    def __init__(self):
        super().__init__("Approval task not found")


class TaskNotActionableError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "TASK_NOT_ACTIONABLE"

    def __init__(self, reason: str):
        super().__init__(reason)
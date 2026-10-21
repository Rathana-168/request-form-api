from fastapi import status

from app.core.exceptions import AppException


class NoActiveWorkflowError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "NO_ACTIVE_WORKFLOW"

    def __init__(self, form_code: str):
        super().__init__(f"Form '{form_code}' has no active workflow")


class ActionNotAllowedError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "ACTION_NOT_ALLOWED"

    def __init__(self, action: str, step_name: str):
        super().__init__(f"'{action}' is not allowed at step '{step_name}'")


class CommentRequiredError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "COMMENT_REQUIRED"

    def __init__(self, action: str):
        super().__init__(f"A comment is required to {action}")
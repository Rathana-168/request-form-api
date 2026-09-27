from app.core.exceptions import AppException, ConflictError, NotFoundError


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"

    def __init__(self):
        super().__init__("User not found")


class EmailAlreadyExistsError(ConflictError):
    code = "EMAIL_ALREADY_EXISTS"

    def __init__(self):
        super().__init__("Email is already registered")


class InvalidReferenceError(AppException):
    code = "INVALID_REFERENCE"  # unknown department / manager / role id


class InvalidManagerError(AppException):
    code = "INVALID_MANAGER"  # self-manager or reporting loop

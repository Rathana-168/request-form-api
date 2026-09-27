from app.core.exceptions import AppException, ConflictError, NotFoundError


class FormNotFoundError(NotFoundError):
    code = "FORM_NOT_FOUND"

    def __init__(self):
        super().__init__("Form not found")


class FormCodeExistsError(ConflictError):
    code = "FORM_CODE_EXISTS"

    def __init__(self):
        super().__init__("A form with this code already exists")


class FormInactiveError(AppException):
    code = "FORM_INACTIVE"

    def __init__(self):
        super().__init__("This form is not accepting requests")


class UnknownFormError(NotFoundError):
    code = "UNKNOWN_FORM"

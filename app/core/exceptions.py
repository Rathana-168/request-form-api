from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.integrations.base import ServiceUnavailableError
from app.shared.schemas import APIResponse


class AppException(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "APP_ERROR"

    def __init__(self, message: str = "Application error"):
        self.message = message


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class PermissionDeniedError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


class UnauthorizedError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(_: Request, exc: ServiceUnavailableError):
        return JSONResponse(
            status_code=503,
            content=APIResponse(success=False, message=f"{exc.service} is unavailable").model_dump(),
        )

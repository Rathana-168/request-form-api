from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.context import TRACE_HEADER
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
    

class UnprocessableError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "UNPROCESSABLE"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError):
        tid = _get_trace_id(request)
        return JSONResponse(
            status_code=503,
            content=APIResponse(success=False, message=f"{exc.service} is unavailable", trace_id=tid).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        tid = _get_trace_id(request)
        body = APIResponse(status_code=500, message="Internal server error", trace_id=tid)
        return JSONResponse(body.model_dump(), status_code=500,
                            headers={TRACE_HEADER: tid} if tid else None)


def _get_trace_id(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None)

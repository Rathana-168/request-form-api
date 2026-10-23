import logging
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import TRACE_HEADER, use_trace_id

log = logging.getLogger("app.access")
SKIP_PATHS = {"/health", "/ready"}


class TraceIdMiddleware:
    """Pure ASGI: sets the trace ID for the whole request and writes the access log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http": # websockets/lifespan: pass through
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(TRACE_HEADER)
        with use_trace_id(incoming) as tid:
            scope.setdefault("state", {})["trace_id"] = tid   # for the 500 handler
            start = time.perf_counter()
            status = 500

            async def send_with_header(message: Message) -> None:
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                    MutableHeaders(scope=message).append(TRACE_HEADER, tid)
                await send(message)

            try:
                await self.app(scope, receive, send_with_header)
            except Exception:
                log.exception("unhandled error")              # traceback carries the trace ID
                raise
            finally:
                if scope["path"] not in SKIP_PATHS:
                    log.info(
                        "%s %s %s", scope["method"], scope["path"], status,
                        extra={"method": scope["method"], "path": scope["path"], "status": status,
                               "ms": round((time.perf_counter() - start) * 1000, 1)},
                    )
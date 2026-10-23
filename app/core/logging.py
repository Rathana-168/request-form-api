from datetime import UTC, datetime
import json
import logging
import sys

from app.core.config import get_settings
from app.core.context import trace_id_var

NOISY = ("httpx", "httpcore", "aiokafka", "asyncio")
TEXT_FMT = "%(asctime)s %(levelname)s [%(trace_id)s] [%(name)s] %(message)s"
EXTRA_KEYS = {"method", "path", "status", "ms", "event_id", "event_type", "email_id", "request_no"}


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(r.created, UTC).isoformat(),
            "level": r.levelname,
            "logger": r.name,
            "msg": r.getMessage(),
            "trace_id": getattr(r, "trace_id", None),
        }
        data.update({k: v for k, v in r.__dict__.items() if k in EXTRA_KEYS})
        if r.exc_info:
            data["exc"] = self.formatException(r.exc_info)
        return json.dumps(data, default=str)


def setup_logging() -> None:
    settings = get_settings()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(JsonFormatter() if settings.LOG_FORMAT == "json"
                         else logging.Formatter(TEXT_FMT))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    # your own code: DEBUG when developing
    logging.getLogger("app").setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # SQL: only when asked for, and only through our handler
    sql = logging.getLogger("sqlalchemy.engine")
    sql.setLevel(logging.INFO if settings.DB_ECHO else logging.WARNING)
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine"):
        logging.getLogger(name).handlers.clear()

    # uvicorn: errors through our handler; access log comes from TraceIdMiddleware
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    for name in NOISY:                                 # third-party chatter
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

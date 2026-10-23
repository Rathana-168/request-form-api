from collections.abc import Generator
from contextlib import contextmanager
import re
import uuid
from contextvars import ContextVar

# Set by get_current_user; None in scripts, Celery tasks and unauthenticated calls.
current_user_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_user_id", default=None
)
trace_id_var: ContextVar[str | None] = ContextVar(
    "trace_id", default=None
)

TRACE_HEADER = "X-Trace-ID"
_VALID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def clean_trace_id(value: str | None) -> str:
    """Use the caller's ID only if it's safe to log; otherwise make a new one."""
    return value if value and _VALID.fullmatch(value) else new_trace_id()


@contextmanager
def use_trace_id(value: str | None) -> Generator[str]:
    """Set the trace ID for a block of work, and always restore it afterwards."""
    tid = clean_trace_id(value)
    token = trace_id_var.set(tid)
    try:
        yield tid
    finally:
        trace_id_var.reset(token)
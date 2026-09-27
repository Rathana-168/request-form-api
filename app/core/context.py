import uuid
from contextvars import ContextVar

# Set by get_current_user; None in scripts, Celery tasks and unauthenticated calls.
current_user_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_user_id", default=None
)

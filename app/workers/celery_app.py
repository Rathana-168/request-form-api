import importlib
import pkgutil
from typing import Any
from contextvars import Token

from celery import Celery
from celery.signals import (
    before_task_publish,
    setup_logging as celery_setup_logging,
    task_postrun,
    task_prerun,
)

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.context import clean_trace_id, trace_id_var
from app.workers import tasks as tasks_pkg

settings = get_settings()

_tokens: dict[str, Token] = {}

celery_app = Celery(
    "workflow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def _discover_tasks() -> tuple[list[str], dict[str, Any]]:
    """Import every module in app/workers/tasks/ and collect its SCHEDULE."""
    modules: list[str] = []
    schedule: dict[str, Any] = {}
    for info in pkgutil.iter_modules(tasks_pkg.__path__):
        module = importlib.import_module(f"{tasks_pkg.__name__}.{info.name}")
        modules.append(module.__name__)
        for key, entry in getattr(module, "SCHEDULE", {}).items():
            if key in schedule:
                raise RuntimeError(f"Duplicate beat schedule '{key}' in {module.__name__}")
            schedule[key] = entry
    return modules, schedule


@celery_setup_logging.connect
def _logging(**_: Any) -> None:
    """Stop Celery replacing our logging config."""
    setup_logging()


@before_task_publish.connect
def _attach_trace_id(headers: dict | None = None, **_: Any) -> None:
    """Sender side: copy the current trace ID into the task message."""
    if headers is not None and (tid := trace_id_var.get()):
        headers["trace_id"] = tid


@task_prerun.connect
def _set_trace_id(task_id: str | None = None, task: Any = None, **_: Any) -> None:
    """Worker side: set the ID before the task runs. Beat tasks fall back to the task ID."""
    tid = clean_trace_id(task.request.get("trace_id") or task_id)
    _tokens[task_id] = trace_id_var.set(tid)


@task_postrun.connect
def _reset_trace_id(task_id: str | None = None, **_: Any) -> None:
    """Worker side: restore after the task, success or failure."""
    if (token := _tokens.pop(task_id, None)) is not None:
        trace_id_var.reset(token)


_modules, _schedule = _discover_tasks()
celery_app.conf.include = _modules
celery_app.conf.beat_schedule = _schedule
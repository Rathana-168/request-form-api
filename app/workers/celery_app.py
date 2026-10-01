import importlib
import pkgutil
from typing import Any

from celery import Celery

from app.core.config import get_settings
from app.workers import tasks as tasks_pkg

settings = get_settings()

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


_modules, _schedule = _discover_tasks()
celery_app.conf.include = _modules
celery_app.conf.beat_schedule = _schedule
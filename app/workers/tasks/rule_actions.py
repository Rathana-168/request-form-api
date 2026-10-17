import asyncio
from datetime import timedelta

from celery import shared_task

import app.rules.actions  # noqa: F401  (registers the action types in the worker)
from app.core.config import settings
from app.db.session import task_sessions
from app.rules.runner import run_pending

SCHEDULE = {
    "rule-actions": {
        "task": "workflow.rule_actions",
        "schedule": timedelta(seconds=settings.RULE_ACTIONS_POLL_SECONDS),
    },
}


async def run_rule_actions() -> dict[str, int]:
    async with task_sessions() as sessions:
        return await run_pending(sessions)


@shared_task(name="workflow.rule_actions", ignore_result=True)
def rule_actions() -> dict[str, int]:
    return asyncio.run(run_rule_actions())


if __name__ == "__main__":
    print(asyncio.run(run_rule_actions()))
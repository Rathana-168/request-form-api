import asyncio
import logging
from datetime import UTC, datetime

from celery import shared_task

from app.core.config import get_settings
from app.db.session import task_sessions
from app.workers.schedules import cron
from app.workflow import sla

logger = logging.getLogger(__name__)


async def run_sla_check() -> dict[str, int]:
    counts = {"reminded": 0, "escalated": 0, "failed": 0}
    now = datetime.now(UTC)

    async with task_sessions() as Session:
        async with Session() as db:
            task_ids = await sla.find_due_task_ids(db, now)

        for task_id in task_ids:
            async with Session() as db:
                try:
                    result = await sla.process_task(db, task_id, now)
                    await db.commit()
                    if result:
                        counts[result] += 1
                except Exception:
                    await db.rollback()
                    counts["failed"] += 1
                    logger.exception("SLA check failed for task %s", task_id)

    if any(counts.values()):
        logger.info("SLA check: %s", counts)
    return counts


SCHEDULE = {
    "workflow-sla-check": {
        "task": "workflow.sla_check",
        "schedule": cron(get_settings().SLA_CHECK_CRON),
    },
}


@shared_task(name="workflow.sla_check")
def sla_check() -> dict[str, int]:
    return asyncio.run(run_sla_check())


if __name__ == "__main__":
    print(asyncio.run(run_sla_check()))

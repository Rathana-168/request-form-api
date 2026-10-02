import asyncio
import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.db.session import task_sessions
from app.events.models import OutboxEvent
from app.workers.schedules import cron

log = logging.getLogger(__name__)

settings = get_settings()

SCHEDULE = {
    "outbox-cleanup": {
        "task": "workflow.outbox_cleanup",
        "schedule": cron(settings.OUTBOX_CLEANUP_CRON),
    },
}

BATCH = 5000


async def run_outbox_cleanup() -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=settings.OUTBOX_RETENTION_DAYS)
    deleted = 0
    async with task_sessions() as sessions:
        async with sessions() as db:
            while True:  # small batches, so the table is never locked for long
                ids = select(OutboxEvent.id).where(
                    OutboxEvent.published_at < cutoff
                ).limit(BATCH).scalar_subquery()
                result = await db.execute(delete(OutboxEvent).where(OutboxEvent.id.in_(ids)))
                await db.commit()
                deleted += result.rowcount
                if result.rowcount < BATCH:
                    break

            # warn if events are stuck (Kafka down, topic missing...)
            oldest = await db.scalar(
                select(func.min(OutboxEvent.created_at)).where(OutboxEvent.published_at.is_(None))
            )
            if oldest and oldest < datetime.now(UTC) - timedelta(minutes=settings.OUTBOX_STUCK_MINUTES):
                log.error("Outbox has unpublished events since %s", oldest)
    return {"deleted": deleted}


@shared_task(name="workflow.outbox_cleanup")
def outbox_cleanup() -> dict[str, int]:
    return asyncio.run(run_outbox_cleanup())


if __name__ == "__main__":
    print(asyncio.run(run_outbox_cleanup()))
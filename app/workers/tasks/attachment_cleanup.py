import asyncio
import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlalchemy import and_, delete, exists, select

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import task_sessions
from app.integrations.base import ServiceUnavailableError
from app.integrations.registry import file_service
from app.modules.attachments.models import Attachment
from app.workers.schedules import cron

log = logging.getLogger(__name__)

settings = get_settings()

SCHEDULE = {
    "attachment-cleanup": {
        "task": "workflow.attachment_cleanup",
        "schedule": cron(settings.ATTACHMENT_CLEANUP_CRON),
    },
}
BATCH = 200


def _not_referenced():
    """NOT EXISTS for every column that has a foreign key to attachments.id."""
    att_id = Attachment.__table__.c.id
    checks = [
        ~exists().where(fk.parent == att_id)
        for table in Base.metadata.sorted_tables
        for fk in table.foreign_keys
        if fk.column is att_id
    ]
    return and_(*checks)


async def run_attachment_cleanup() -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(hours=settings.ATTACHMENT_UNUSED_HOURS)
    deleted = failed = 0
    async with task_sessions() as sessions, sessions() as db:
        stmt = (
            select(Attachment.id)
            .where(Attachment.created_at < cutoff, _not_referenced())
            .limit(BATCH)
        )
        if settings.ATTACHMENT_USE_REQUEST_ID:          # if you keep attachments.request_id
            stmt = stmt.where(Attachment.request_id.is_(None))
        for file_id in list(await db.scalars(stmt)):
            try:
                await file_service.delete(file_id)       # file first ...
            except ServiceUnavailableError:
                failed += 1
                continue                                 # ... keep the row, retry next run
            await db.execute(delete(Attachment).where(Attachment.id == file_id))
            await db.commit()
            deleted += 1
    if failed:
        log.warning("Attachment cleanup: %s files could not be deleted", failed)
    return {"deleted": deleted, "failed": failed}


@shared_task(name="workflow.attachment_cleanup")
def attachment_cleanup() -> dict[str, int]:
    return asyncio.run(run_attachment_cleanup())


if __name__ == "__main__":
    print(asyncio.run(run_attachment_cleanup()))
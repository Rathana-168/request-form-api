import logging
from datetime import UTC, datetime

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.events.models import OutboxEvent

log = logging.getLogger(__name__)

RELAY_LOCK_ID = 910_001  # any constant; only one relay may run at a time


async def relay_batch(db: AsyncSession, producer: AIOKafkaProducer) -> int:
    if not await db.scalar(select(func.pg_try_advisory_xact_lock(RELAY_LOCK_ID))):
        return 0  # another relay run is busy

    rows = (await db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.seq)
        .limit(get_settings().OUTBOX_BATCH_SIZE)
    )).all()

    sent = 0
    for event in rows:
        try:
            await producer.send_and_wait(
                event.topic, value=event.payload, key=event.key,
                headers=[("event_type", event.event_type.encode())],
            )
        except KafkaError as exc:
            event.attempts += 1
            event.last_error = str(exc)[:1000]
            log.warning("Outbox publish failed for %s: %s", event.id, exc)
            break  # keep order: don't send later events before this one
        event.published_at = datetime.now(UTC)
        sent += 1

    await db.commit()
    return sent
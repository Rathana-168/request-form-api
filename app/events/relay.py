import logging
from datetime import UTC, datetime

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.context import use_trace_id
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
        with use_trace_id(event.trace_id):
            try:
                await producer.send_and_wait(
                    event.topic, value=event.payload, key=event.key,
                    headers=_headers(event),
                )
            except KafkaError as exc:
                event.attempts += 1
                event.last_error = str(exc)[:1000]
                log.warning("Outbox publish failed for %s: %s", event.id, exc,
                            extra={"event_type": event.event_type})
                break  # keep order: don't send later events before this one
            event.published_at = datetime.now(UTC)
            log.debug("Outbox published %s", event.id,
                      extra={"event_type": event.event_type})
        sent += 1

    await db.commit()
    return sent


def _headers(event: OutboxEvent) -> list[tuple[str, bytes]]:
    headers = [("event_type", event.event_type.encode())]
    if event.trace_id:
        headers.append(("trace_id", event.trace_id.encode()))
    return headers
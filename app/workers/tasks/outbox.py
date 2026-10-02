import asyncio
from datetime import timedelta

from celery import shared_task

from app.core.config import get_settings
from app.db.session import task_sessions
from app.events.kafka import kafka_producer
from app.events.relay import relay_batch

settings = get_settings()

SCHEDULE = {
    "outbox-relay": {
        "task": "workflow.outbox_relay",
        "schedule": timedelta(seconds=settings.OUTBOX_RELAY_SECONDS),
    },
}


async def run_outbox_relay() -> dict[str, int]:
    published = 0
    async with task_sessions() as sessions, kafka_producer() as producer:
        while True:  # keep going until the backlog is empty
            async with sessions() as db:
                sent = await relay_batch(db, producer)
            published += sent
            if sent < settings.OUTBOX_BATCH_SIZE:
                break
    return {"published": published}


@shared_task(name="workflow.outbox_relay", ignore_result=True)
def outbox_relay() -> dict[str, int]:
    return asyncio.run(run_outbox_relay())


if __name__ == "__main__":
    print(asyncio.run(run_outbox_relay()))
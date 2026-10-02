import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer

from app.core.config import get_settings


@asynccontextmanager
async def kafka_producer() -> AsyncGenerator[AIOKafkaProducer]:
    producer = AIOKafkaProducer(
        bootstrap_servers=get_settings().KAFKA_BOOTSTRAP_SERVERS,
        acks="all",                 # wait until all replicas have the message
        enable_idempotence=True,    # a retry by the producer can't create duplicates
        key_serializer=lambda k: k.encode(),
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()
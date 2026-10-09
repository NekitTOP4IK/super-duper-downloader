from collections.abc import AsyncIterator, Awaitable, Callable

from app.api.schemas import BatchState
from app.models import Batch
from app.store.redis_store import Store, events_channel


def sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


async def batch_events(
    store: Store,
    batch: Batch,
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    heartbeat: float = 15.0,
) -> AsyncIterator[str]:
    pubsub = store.redis.pubsub()
    # Subscribe before taking the snapshot so no update can slip in between.
    await pubsub.subscribe(events_channel(batch.id))
    try:
        jobs = await store.list_jobs(batch.id)
        yield sse("snapshot", BatchState(batch=batch, jobs=jobs).model_dump_json())
        while not await is_disconnected():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=heartbeat)
            if message is None:
                yield ": ping\n\n"
                continue
            data = message["data"]
            yield sse("job", data.decode() if isinstance(data, bytes) else data)
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()

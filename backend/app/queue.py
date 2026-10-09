from datetime import timedelta
from typing import Any, Protocol

from arq.connections import ArqRedis

DOWNLOAD_QUEUE = "sdd:downloads"
PROBE_QUEUE = "sdd:probe"


class TaskQueue(Protocol):
    async def enqueue_download(self, job_id: str) -> None: ...

    async def download_queue_length(self) -> int: ...

    async def probe_queue_length(self) -> int: ...

    async def probe(self, url: str, timeout: float) -> dict[str, Any]: ...


class ArqTaskQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue_download(self, job_id: str) -> None:
        await self._pool.enqueue_job("process_job", job_id, _queue_name=DOWNLOAD_QUEUE)

    async def download_queue_length(self) -> int:
        return await self._pool.zcard(DOWNLOAD_QUEUE)

    async def probe_queue_length(self) -> int:
        return await self._pool.zcard(PROBE_QUEUE)

    async def probe(self, url: str, timeout: float) -> dict[str, Any]:
        job = await self._pool.enqueue_job(
            "probe_url", url, _queue_name=PROBE_QUEUE, _expires=timedelta(seconds=timeout)
        )
        if job is None:
            raise RuntimeError("probe job was not enqueued")
        return await job.result(timeout=timeout)

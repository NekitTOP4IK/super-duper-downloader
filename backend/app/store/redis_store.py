import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.models import Batch, Job, MediaInfo, Preset


def new_id(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)


def events_channel(batch_id: str) -> str:
    return f"events:{batch_id}"


def _batch_key(batch_id: str) -> str:
    return f"batch:{batch_id}"


def _jobs_key(batch_id: str) -> str:
    return f"batch:{batch_id}:jobs"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _probe_key(url: str) -> str:
    return f"probe:{hashlib.sha256(url.encode()).hexdigest()}"


def _ts(moment: datetime) -> int:
    return int(moment.timestamp())


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


class Store:
    def __init__(self, redis: Redis, ttl_sec: int) -> None:
        self._redis = redis
        self._ttl_sec = ttl_sec

    @property
    def redis(self) -> Redis:
        return self._redis

    async def create_batch(
        self, preset: Preset, urls: list[str], owner_id: str | None = None
    ) -> tuple[Batch, list[Job]]:
        now = datetime.now(UTC)
        batch = Batch(
            id=new_id(),
            owner_id=owner_id,
            preset=preset,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_sec),
        )
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_batch_key(batch.id), batch.model_dump_json())
            pipe.expireat(_batch_key(batch.id), _ts(batch.expires_at))
            await pipe.execute()
        jobs = await self.add_jobs(batch, urls)
        return batch, jobs

    async def add_jobs(
        self, batch: Batch, urls: list[str], parent_id: str | None = None
    ) -> list[Job]:
        jobs = [
            Job(
                id=new_id(12),
                batch_id=batch.id,
                url=url,
                parent_id=parent_id,
                expires_at=batch.expires_at,
            )
            for url in urls
        ]
        if not jobs:
            return []
        expire_at = _ts(batch.expires_at)
        async with self._redis.pipeline(transaction=True) as pipe:
            for job in jobs:
                payload = job.model_dump_json()
                pipe.set(_job_key(job.id), payload)
                pipe.expireat(_job_key(job.id), expire_at)
                pipe.publish(events_channel(batch.id), payload)
            pipe.rpush(_jobs_key(batch.id), *[job.id for job in jobs])
            pipe.expireat(_jobs_key(batch.id), expire_at)
            await pipe.execute()
        return jobs

    async def get_batch(self, batch_id: str) -> Batch | None:
        raw = await self._redis.get(_batch_key(batch_id))
        return Batch.model_validate_json(raw) if raw else None

    async def batch_exists(self, batch_id: str) -> bool:
        return bool(await self._redis.exists(_batch_key(batch_id)))

    async def get_job(self, job_id: str) -> Job | None:
        raw = await self._redis.get(_job_key(job_id))
        return Job.model_validate_json(raw) if raw else None

    async def list_jobs(self, batch_id: str) -> list[Job]:
        ids = await self._redis.lrange(_jobs_key(batch_id), 0, -1)
        if not ids:
            return []
        raws = await self._redis.mget([_job_key(_text(job_id)) for job_id in ids])
        return [Job.model_validate_json(raw) for raw in raws if raw]

    async def save_job(self, job: Job) -> None:
        payload = job.model_dump_json()
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_job_key(job.id), payload)
            pipe.expireat(_job_key(job.id), _ts(job.expires_at))
            pipe.publish(events_channel(job.batch_id), payload)
            await pipe.execute()

    async def get_probe(self, url: str) -> MediaInfo | None:
        raw = await self._redis.get(_probe_key(url))
        return MediaInfo.model_validate_json(raw) if raw else None

    async def set_probe(self, url: str, info: MediaInfo, ttl_sec: int) -> None:
        await self._redis.set(_probe_key(url), info.model_dump_json(), ex=ttl_sec)

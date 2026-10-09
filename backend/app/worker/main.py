import logging
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.engines.factory import build_router
from app.queue import DOWNLOAD_QUEUE, PROBE_QUEUE, ArqTaskQueue
from app.store.redis_store import Store
from app.worker.cleanup import sweep_expired
from app.worker.jobs import run_job, run_probe

settings = get_settings()
redis_settings = RedisSettings.from_dsn(settings.redis_url)


async def startup(ctx: dict[str, Any]) -> None:
    logging.basicConfig(level=logging.INFO)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    ctx["store"] = Store(ctx["redis"], settings.file_ttl_sec)
    ctx["router"] = build_router(settings)
    ctx["queue"] = ArqTaskQueue(ctx["redis"])


async def probe_url(ctx: dict[str, Any], url: str) -> dict[str, Any]:
    return await run_probe(ctx["store"], ctx["router"], settings, url)


async def process_job(ctx: dict[str, Any], job_id: str) -> None:
    await run_job(ctx["store"], ctx["router"], ctx["queue"], settings, job_id)


async def cleanup(ctx: dict[str, Any]) -> None:
    await sweep_expired(ctx["store"], settings.data_dir)


class DownloadWorker:
    functions = [func(process_job, timeout=settings.job_timeout_sec, max_tries=2)]
    cron_jobs = [cron(cleanup, minute=set(range(0, 60, 5)))]
    queue_name = DOWNLOAD_QUEUE
    max_jobs = settings.worker_concurrency
    redis_settings = redis_settings
    on_startup = startup


class ProbeWorker:
    functions = [func(probe_url, timeout=settings.probe_timeout_sec + 30, max_tries=1)]
    queue_name = PROBE_QUEUE
    max_jobs = settings.probe_concurrency
    redis_settings = redis_settings
    on_startup = startup

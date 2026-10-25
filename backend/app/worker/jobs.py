import asyncio
import contextlib
import logging
import shutil
from typing import Any

from app import gif
from app.core.config import Settings
from app.core.errors import EngineError, ErrorCode
from app.core.paths import job_dir
from app.engines.base import DownloadOptions
from app.engines.router import EngineRouter
from app.models import (
    Batch,
    FileInfo,
    Job,
    JobError,
    JobStatus,
    MediaInfo,
    MediaKind,
    Preset,
    Progress,
)
from app.queue import TaskQueue
from app.store.redis_store import Store

log = logging.getLogger(__name__)


async def run_probe(
    store: Store, router: EngineRouter, settings: Settings, url: str
) -> dict[str, Any]:
    info = await store.get_probe(url)
    if info is None:
        try:
            info = await router.probe(url)
        except EngineError as exc:
            return _probe_error(exc.code, exc.message)
        await store.set_probe(url, info, settings.probe_cache_sec)
    if _too_long(info, settings):
        return _probe_error(
            ErrorCode.TOO_LONG, f"media is longer than {settings.max_duration_sec} seconds"
        )
    return {"ok": True, "info": info.model_dump(mode="json")}


class ProgressReporter:
    def __init__(self, store: Store, job: Job, interval: float = 1.0) -> None:
        self._store = store
        self._job = job
        self._interval = interval
        self._latest: Progress | None = None
        self._sent: Progress | None = None
        self._task: asyncio.Task[None] | None = None

    def __call__(self, progress: Progress) -> None:
        # Called from yt-dlp's worker thread; a single attribute assignment is atomic in CPython.
        self._latest = progress

    async def __aenter__(self) -> "ProgressReporter":
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def flush(self) -> None:
        latest = self._latest
        if latest is None or latest is self._sent:
            return
        self._sent = latest
        self._job.progress = latest
        self._job.status = (
            JobStatus.PROCESSING if latest.stage == "processing" else JobStatus.DOWNLOADING
        )
        await self._store.save_job(self._job)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self.flush()


async def run_job(
    store: Store, router: EngineRouter, queue: TaskQueue, settings: Settings, job_id: str
) -> None:
    job = await store.get_job(job_id)
    if job is None or job.status in (JobStatus.DONE, JobStatus.EXPANDED):
        return
    batch = await store.get_batch(job.batch_id)
    if batch is None:
        return
    try:
        info = await store.get_probe(job.url) or await router.probe(job.url)
        job.title = info.title
        if info.kind is MediaKind.PLAYLIST:
            await _expand(store, queue, settings, batch, job, info)
        else:
            if _too_long(info, settings):
                raise EngineError(
                    ErrorCode.TOO_LONG, f"media is longer than {settings.max_duration_sec} seconds"
                )
            await _download(store, router, settings, batch, job)
    except EngineError as exc:
        await _fail(store, job, exc.code, exc.message)
    except Exception:
        log.exception("job %s crashed", job.id)
        await _fail(store, job, ErrorCode.INTERNAL, "unexpected error")


async def _expand(
    store: Store, queue: TaskQueue, settings: Settings, batch: Batch, job: Job, info: MediaInfo
) -> None:
    if job.parent_id is not None:
        raise EngineError(ErrorCode.UNSUPPORTED, "nested playlists are not supported")
    urls = [entry.url for entry in info.entries][: settings.max_playlist_items]
    if not urls:
        raise EngineError(ErrorCode.EXTRACTION_FAILED, "playlist is empty")
    children = await store.add_jobs(batch, urls, parent_id=job.id)
    job.status = JobStatus.EXPANDED
    await store.save_job(job)
    for child in children:
        await queue.enqueue_download(child.id)


async def _download(
    store: Store, router: EngineRouter, settings: Settings, batch: Batch, job: Job
) -> None:
    dest = job_dir(settings.data_dir, batch.id, job.id)
    opts = DownloadOptions(
        preset=batch.preset,
        dest_dir=dest,
        max_duration_sec=settings.max_duration_sec,
        max_filesize_bytes=settings.max_filesize_bytes,
    )
    job.status = JobStatus.DOWNLOADING
    job.error = None
    await store.save_job(job)
    async with ProgressReporter(store, job) as reporter:
        engine_name, paths = await router.download(job.url, opts, reporter)
        if batch.preset is Preset.GIF:
            reporter(Progress(stage="processing"))
            paths = [await gif.convert(path) for path in paths]
    shutil.rmtree(dest / ".part", ignore_errors=True)
    job.engine = engine_name
    job.files = [FileInfo(name=path.name, size=path.stat().st_size) for path in paths]
    job.status = JobStatus.DONE
    job.progress = None
    await store.save_job(job)


async def _fail(store: Store, job: Job, code: ErrorCode, message: str) -> None:
    job.status = JobStatus.FAILED
    job.progress = None
    job.error = JobError(code=code, message=message)
    await store.save_job(job)


def _too_long(info: MediaInfo, settings: Settings) -> bool:
    return (
        info.kind is MediaKind.SINGLE
        and info.duration is not None
        and info.duration > settings.max_duration_sec
    )


def _probe_error(code: ErrorCode, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code.value, "message": message}}

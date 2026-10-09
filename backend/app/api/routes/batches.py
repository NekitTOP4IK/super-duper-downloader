from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse

from app.api import guards
from app.api.archive import build_zip
from app.api.deps import ID_PATTERN, QueueDep, Requester, RequesterDep, SettingsDep, StoreDep
from app.api.errors import ApiErrorCode, api_error
from app.api.events import batch_events
from app.api.schemas import BatchCreated, BatchRequest, BatchState
from app.core.config import Settings
from app.core.urls import extract_urls
from app.models import Batch, Preset
from app.queue import TaskQueue
from app.store.redis_store import Store

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 1_000_000

BatchId = Annotated[str, PathParam(pattern=ID_PATTERN)]


@router.post("/batches", status_code=201)
async def create_batch(
    body: BatchRequest,
    settings: SettingsDep,
    store: StoreDep,
    queue: QueueDep,
    requester: RequesterDep,
) -> BatchCreated:
    text = "\n".join([*body.urls, body.text])
    return await _create(text, body.preset, settings, store, queue, requester)


@router.post("/batches/upload", status_code=201)
async def upload_batch(
    file: UploadFile,
    settings: SettingsDep,
    store: StoreDep,
    queue: QueueDep,
    requester: RequesterDep,
    preset: Annotated[Preset, Form()] = Preset.BEST,
) -> BatchCreated:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise api_error(413, ApiErrorCode.UPLOAD_TOO_LARGE, "file is larger than 1 MB")
    text = raw.decode("utf-8", errors="replace")
    return await _create(text, preset, settings, store, queue, requester)


async def _create(
    text: str,
    preset: Preset,
    settings: Settings,
    store: Store,
    queue: TaskQueue,
    requester: Requester,
) -> BatchCreated:
    urls = extract_urls(text)
    if not urls:
        raise api_error(422, ApiErrorCode.NO_URLS, "no http(s) URL found")
    truncated = len(urls) > settings.max_batch_urls
    urls = urls[: settings.max_batch_urls]
    await guards.ensure_download_capacity(settings, queue)
    batch, jobs = await store.create_batch(preset, urls, owner_id=requester.id)
    for job in jobs:
        await queue.enqueue_download(job.id)
    return BatchCreated(batch_id=batch.id, jobs=len(jobs), truncated=truncated)


async def _require_batch(store: Store, batch_id: str) -> Batch:
    batch = await store.get_batch(batch_id)
    if batch is None:
        raise api_error(404, ApiErrorCode.NOT_FOUND, "batch not found or expired")
    return batch


@router.get("/batches/{batch_id}")
async def get_batch_state(batch_id: BatchId, store: StoreDep) -> BatchState:
    batch = await _require_batch(store, batch_id)
    return BatchState(batch=batch, jobs=await store.list_jobs(batch_id))


@router.get("/batches/{batch_id}/events")
async def stream_batch_events(
    batch_id: BatchId, request: Request, store: StoreDep
) -> StreamingResponse:
    batch = await _require_batch(store, batch_id)
    return StreamingResponse(
        batch_events(store, batch, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/batches/{batch_id}/zip")
async def download_zip(
    batch_id: BatchId, store: StoreDep, settings: SettingsDep
) -> StreamingResponse:
    await _require_batch(store, batch_id)
    archive = build_zip(settings.data_dir, await store.list_jobs(batch_id))
    if archive is None:
        raise api_error(404, ApiErrorCode.NO_FILES, "no finished files in this batch")
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{batch_id}.zip"',
            "Content-Length": str(len(archive)),
        },
    )

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi import Path as PathParam
from fastapi.responses import FileResponse

from app.api.deps import ID_PATTERN, SettingsDep, StoreDep
from app.api.errors import ApiErrorCode, api_error
from app.core.paths import download_name, resolve_file
from app.models import JobStatus

router = APIRouter(prefix="/api")

JobId = Annotated[str, PathParam(pattern=ID_PATTERN)]


@router.get("/files/{job_id}")
async def download_file(
    job_id: JobId,
    store: StoreDep,
    settings: SettingsDep,
    i: Annotated[int, Query(ge=0)] = 0,
) -> FileResponse:
    job = await store.get_job(job_id)
    if job is None or job.status is not JobStatus.DONE or i >= len(job.files):
        raise api_error(404, ApiErrorCode.NOT_FOUND, "file not found or expired")
    path = resolve_file(settings.data_dir, job, job.files[i].name)
    if path is None:
        raise api_error(404, ApiErrorCode.NOT_FOUND, "file not found or expired")
    return FileResponse(path, filename=download_name(job.files[i].name))

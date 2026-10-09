import shutil
from pathlib import Path

from app.api.errors import ApiErrorCode, api_error
from app.core.config import Settings
from app.queue import TaskQueue


def free_disk_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024**3


async def ensure_download_capacity(settings: Settings, queue: TaskQueue) -> None:
    if await queue.download_queue_length() >= settings.max_queue:
        raise api_error(503, ApiErrorCode.BUSY, "server is busy, try again later")
    if free_disk_gb(settings.data_dir) < settings.min_free_disk_gb:
        raise api_error(503, ApiErrorCode.BUSY, "server is out of disk space, try again later")

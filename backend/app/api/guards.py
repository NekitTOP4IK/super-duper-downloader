import shutil
from pathlib import Path

from app.api.deps import Requester
from app.api.errors import ApiErrorCode, api_error
from app.core.config import Settings
from app.queue import TaskQueue
from app.store.redis_store import Store


def free_disk_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1024**3


async def ensure_download_capacity(settings: Settings, queue: TaskQueue) -> None:
    if await queue.download_queue_length() >= settings.max_queue:
        raise api_error(503, ApiErrorCode.BUSY, "server is busy, try again later")
    if free_disk_gb(settings.data_dir) < settings.min_free_disk_gb:
        raise api_error(503, ApiErrorCode.BUSY, "server is out of disk space, try again later")


async def ensure_within_rate(
    store: Store, requester: Requester, action: str, amount: int, limit: int, window_sec: int
) -> None:
    """Counts amount against a per-address limit, which 0 turns off."""
    if limit <= 0:
        return
    used, wait = await store.add_use(f"{action}:{requester.ip}", amount, window_sec)
    if used > limit:
        raise api_error(
            429,
            ApiErrorCode.RATE_LIMITED,
            f"too many requests from this address, try again in {wait} s",
            headers={"Retry-After": str(wait)},
        )

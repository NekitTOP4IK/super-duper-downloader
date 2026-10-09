import asyncio
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from app.store.redis_store import Store


async def sweep_expired(
    store: Store,
    data_dir: Path,
    *,
    grace_sec: int = 600,
    now: Callable[[], float] = time.time,
) -> int:
    if not data_dir.exists():
        return 0
    removed = 0
    for entry in data_dir.iterdir():
        if not entry.is_dir() or await store.batch_exists(entry.name):
            continue
        # The grace period protects directories of batches being created right now.
        if now() - entry.stat().st_mtime < grace_sec:
            continue
        await asyncio.to_thread(shutil.rmtree, entry, True)
        removed += 1
    return removed

import os
import time

from app.models import Preset
from app.queue import DOWNLOAD_QUEUE, PROBE_QUEUE
from app.worker.cleanup import sweep_expired


async def test_sweep_removes_only_old_orphaned_dirs(store, settings):
    data = settings.data_dir
    data.mkdir(parents=True)
    batch, _ = await store.create_batch(Preset.BEST, ["https://x.example/1"])
    live = data / batch.id
    live.mkdir()
    old_orphan = data / "orphan-old"
    old_orphan.mkdir()
    (old_orphan / "file.bin").write_bytes(b"x")
    fresh_orphan = data / "orphan-new"
    fresh_orphan.mkdir()
    past = time.time() - 3600
    os.utime(live, (past, past))
    os.utime(old_orphan, (past, past))

    removed = await sweep_expired(store, data, grace_sec=600)

    assert removed == 1
    assert live.exists()
    assert not old_orphan.exists()
    assert fresh_orphan.exists()


async def test_sweep_tolerates_missing_data_dir(store, tmp_path):
    assert await sweep_expired(store, tmp_path / "missing") == 0


def test_worker_settings_wire_queues_and_functions():
    from app.worker import main

    assert main.DownloadWorker.queue_name == DOWNLOAD_QUEUE
    assert main.ProbeWorker.queue_name == PROBE_QUEUE
    assert [f.name for f in main.DownloadWorker.functions] == ["process_job"]
    assert [f.name for f in main.ProbeWorker.functions] == ["probe_url"]

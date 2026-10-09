import io
import zipfile

from app.api.events import batch_events
from app.models import FileInfo, JobStatus, Preset
from tests.fakes import make_done_job

URLS = ["https://a.example/1", "https://a.example/2"]


async def test_get_batch_state(client, store):
    batch, jobs = await store.create_batch(Preset.BEST, URLS)
    response = await client.get(f"/api/batches/{batch.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["batch"]["id"] == batch.id
    assert [j["id"] for j in body["jobs"]] == [j.id for j in jobs]


async def test_unknown_batch_is_404(client):
    response = await client.get("/api/batches/unknown-batch-id")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


async def test_malformed_batch_id_is_rejected(client):
    assert (await client.get("/api/batches/bad!id")).status_code == 422


async def test_download_file(client, store, settings):
    batch, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    await make_done_job(store, settings, batch, job, {"clip.mp4": b"VIDEO"})
    response = await client.get(f"/api/files/{job.id}")
    assert response.status_code == 200
    assert response.content == b"VIDEO"
    assert "clip.mp4" in response.headers["content-disposition"]


async def test_file_index_out_of_range_is_404(client, store, settings):
    batch, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    await make_done_job(store, settings, batch, job, {"clip.mp4": b"VIDEO"})
    assert (await client.get(f"/api/files/{job.id}?i=1")).status_code == 404


async def test_unfinished_job_file_is_404(client, store):
    _, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    assert (await client.get(f"/api/files/{job.id}")).status_code == 404


async def test_path_traversal_is_404(client, store, settings):
    _, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    (settings.data_dir / "secret.txt").write_bytes(b"secret")
    job.status = JobStatus.DONE
    job.files = [FileInfo(name="../../secret.txt", size=6)]
    await store.save_job(job)
    assert (await client.get(f"/api/files/{job.id}")).status_code == 404


async def test_zip_contains_done_files_with_unique_names(client, store, settings):
    batch, [first, second] = await store.create_batch(Preset.BEST, URLS)
    await make_done_job(store, settings, batch, first, {"a.mp4": b"1"})
    await make_done_job(store, settings, batch, second, {"a.mp4": b"2"})
    response = await client.get(f"/api/batches/{batch.id}/zip")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == ["a (2).mp4", "a.mp4"]


async def test_zip_without_files_is_404(client, store):
    batch, _ = await store.create_batch(Preset.BEST, URLS)
    response = await client.get(f"/api/batches/{batch.id}/zip")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NO_FILES"


async def next_event(stream):
    for _ in range(50):
        chunk = await anext(stream)
        if not chunk.startswith(":"):
            return chunk
    raise AssertionError("no event received")


async def connected():
    return False


async def test_batch_events_stream_snapshot_then_updates(store):
    batch, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    stream = batch_events(store, batch, connected, heartbeat=0.05)
    snapshot = await anext(stream)
    assert snapshot.startswith("event: snapshot\n")
    job.status = JobStatus.DONE
    await store.save_job(job)
    update = await next_event(stream)
    assert update.startswith("event: job\n")
    assert '"status":"done"' in update
    await stream.aclose()


async def test_batch_events_sends_heartbeat(store):
    batch, _ = await store.create_batch(Preset.BEST, URLS[:1])
    stream = batch_events(store, batch, connected, heartbeat=0.05)
    await anext(stream)
    assert await anext(stream) == ": ping\n\n"
    await stream.aclose()


def test_asgi_entrypoint_exposes_routes():
    from app.api.main import app

    paths = set(app.openapi()["paths"])
    assert {"/api/probe", "/api/batches", "/api/files/{job_id}"} <= paths

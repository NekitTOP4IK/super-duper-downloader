from app.core.errors import EngineError, ErrorCode
from app.engines.router import EngineRouter
from app.models import FileInfo, JobStatus, MediaInfo, MediaKind, PlaylistEntry, Preset, Progress
from app.worker.jobs import ProgressReporter, run_job, run_probe
from tests.fakes import FakeEngine, FakeQueue, make_video, needs_ffmpeg, single, writes_file

URL = "https://example.com/v"


def router_with(engine):
    return EngineRouter([engine])


async def test_run_probe_returns_info_and_caches(store, settings):
    engine = FakeEngine(probe=[single(url=URL, duration=10)])
    first = await run_probe(store, router_with(engine), settings, URL)
    second = await run_probe(store, router_with(engine), settings, URL)
    assert first == second
    assert first["ok"] is True
    assert first["info"]["title"] == "Video"
    assert len(engine.probe_calls) == 1


async def test_run_probe_rejects_too_long(store, settings):
    engine = FakeEngine(probe=[single(url=URL, duration=settings.max_duration_sec + 1)])
    result = await run_probe(store, router_with(engine), settings, URL)
    assert result["ok"] is False
    assert result["error"]["code"] == "TOO_LONG"


async def test_run_probe_reports_engine_error(store, settings):
    engine = FakeEngine(probe=[EngineError(ErrorCode.PRIVATE, "private")])
    result = await run_probe(store, router_with(engine), settings, URL)
    assert result == {"ok": False, "error": {"code": "PRIVATE", "message": "private"}}


async def test_run_job_downloads_single(store, settings):
    engine = FakeEngine("fake", probe=[single()], download=[writes_file("clip.mp4", b"12345")])
    batch, [job] = await store.create_batch(Preset.BEST, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    saved = await store.get_job(job.id)
    assert saved.status is JobStatus.DONE
    assert saved.engine == "fake"
    assert saved.title == "Video"
    assert saved.progress is None
    assert saved.files == [FileInfo(name="clip.mp4", size=5)]
    assert (settings.data_dir / batch.id / job.id / "clip.mp4").read_bytes() == b"12345"


@needs_ffmpeg
async def test_run_job_turns_videos_into_gifs(store, settings, tmp_path):
    video = make_video(tmp_path / "source.mp4").read_bytes()
    engine = FakeEngine(probe=[single()], download=[writes_file("clip.mp4", video)])
    batch, [job] = await store.create_batch(Preset.GIF, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    saved = await store.get_job(job.id)
    assert saved.status is JobStatus.DONE
    assert [file.name for file in saved.files] == ["clip.gif"]
    assert not (settings.data_dir / batch.id / job.id / "clip.mp4").exists()


@needs_ffmpeg
async def test_run_job_fails_a_gif_of_something_that_is_not_a_video(store, settings):
    engine = FakeEngine(probe=[single()], download=[writes_file("song.mp3", b"data")])
    _, [job] = await store.create_batch(Preset.GIF, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    saved = await store.get_job(job.id)
    assert saved.status is JobStatus.FAILED
    assert saved.error.code is ErrorCode.NO_VIDEO


async def test_run_job_records_failure(store, settings):
    engine = FakeEngine(
        probe=[single()], download=[EngineError(ErrorCode.PRIVATE, "private video")]
    )
    _, [job] = await store.create_batch(Preset.BEST, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    saved = await store.get_job(job.id)
    assert saved.status is JobStatus.FAILED
    assert saved.error.code is ErrorCode.PRIVATE
    assert saved.error.message == "private video"


async def test_run_job_rejects_too_long_before_download(store, settings):
    engine = FakeEngine(
        probe=[single(duration=settings.max_duration_sec + 1)], download=[writes_file()]
    )
    _, [job] = await store.create_batch(Preset.BEST, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    assert (await store.get_job(job.id)).error.code is ErrorCode.TOO_LONG
    assert engine.download_calls == []


async def test_run_job_expands_playlist(store, settings):
    settings = settings.model_copy(update={"max_playlist_items": 2})
    playlist = MediaInfo(
        kind=MediaKind.PLAYLIST,
        url="https://pl.example",
        title="PL",
        count=3,
        entries=[PlaylistEntry(url=f"https://v.example/{i}") for i in range(3)],
    )
    queue = FakeQueue()
    batch, [job] = await store.create_batch(Preset.BEST, ["https://pl.example"])
    await run_job(store, router_with(FakeEngine(probe=[playlist])), queue, settings, job.id)
    parent = await store.get_job(job.id)
    assert parent.status is JobStatus.EXPANDED
    assert parent.title == "PL"
    children = [j for j in await store.list_jobs(batch.id) if j.parent_id == job.id]
    assert [c.url for c in children] == ["https://v.example/0", "https://v.example/1"]
    assert queue.downloads == [c.id for c in children]


async def test_run_job_rejects_nested_playlist(store, settings):
    playlist = MediaInfo(kind=MediaKind.PLAYLIST, url="https://pl.example", entries=[])
    batch, [parent] = await store.create_batch(Preset.BEST, ["https://outer.example"])
    [child] = await store.add_jobs(batch, ["https://pl.example"], parent_id=parent.id)
    await run_job(store, router_with(FakeEngine(probe=[playlist])), FakeQueue(), settings, child.id)
    assert (await store.get_job(child.id)).error.code is ErrorCode.UNSUPPORTED


async def test_run_job_ignores_finished_jobs(store, settings):
    engine = FakeEngine(probe=[single()])
    _, [job] = await store.create_batch(Preset.BEST, [URL])
    job.status = JobStatus.DONE
    await store.save_job(job)
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    assert engine.probe_calls == []


async def test_run_job_uses_cached_probe(store, settings):
    await store.set_probe(URL, single(url=URL), 60)
    engine = FakeEngine(probe=[EngineError(ErrorCode.BLOCKED)], download=[writes_file()])
    _, [job] = await store.create_batch(Preset.BEST, [URL])
    await run_job(store, router_with(engine), FakeQueue(), settings, job.id)
    assert (await store.get_job(job.id)).status is JobStatus.DONE
    assert engine.probe_calls == []


async def test_progress_reporter_flush_saves_status(store):
    _, [job] = await store.create_batch(Preset.BEST, [URL])
    reporter = ProgressReporter(store, job)
    reporter(Progress(stage="processing"))
    await reporter.flush()
    assert (await store.get_job(job.id)).status is JobStatus.PROCESSING

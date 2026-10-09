from app.models import FileInfo, JobStatus, MediaInfo, MediaKind, Preset, Progress


def _next(outcomes):
    outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


class FakeEngine:
    def __init__(self, name="fake", *, handles=True, probe=(), download=()):
        self.name = name
        self._handles = handles
        self._probe = list(probe)
        self._download = list(download)
        self.probe_calls: list[str] = []
        self.download_calls: list[str] = []

    def can_handle(self, url):
        return self._handles

    async def probe(self, url):
        self.probe_calls.append(url)
        return _next(self._probe)

    async def download(self, url, opts, on_progress):
        self.download_calls.append(url)
        outcome = _next(self._download)
        return outcome(opts, on_progress) if callable(outcome) else outcome


def single(url="https://example.com/v", **kwargs) -> MediaInfo:
    return MediaInfo(kind=MediaKind.SINGLE, url=url, title="Video", presets=[Preset.BEST], **kwargs)


def writes_file(name="video.mp4", content=b"data"):
    def run(opts, on_progress):
        on_progress(Progress(percent=100.0, downloaded=len(content), total=len(content)))
        path = opts.dest_dir / name
        path.write_bytes(content)
        return [path]

    return run


class FakeQueue:
    def __init__(self, probe_handler=None):
        self.downloads: list[str] = []
        self.download_length = 0
        self.probe_length = 0
        self.probe_handler = probe_handler

    async def enqueue_download(self, job_id):
        self.downloads.append(job_id)

    async def download_queue_length(self):
        return self.download_length

    async def probe_queue_length(self):
        return self.probe_length

    async def probe(self, url, timeout):
        return await self.probe_handler(url)


async def make_done_job(store, settings, batch, job, files):
    directory = settings.data_dir / batch.id / job.id
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_bytes(content)
    job.status = JobStatus.DONE
    job.files = [FileInfo(name=name, size=len(content)) for name, content in files.items()]
    await store.save_job(job)
    return job

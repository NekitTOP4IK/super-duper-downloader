from app.models import MediaInfo, MediaKind, Preset, Progress


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

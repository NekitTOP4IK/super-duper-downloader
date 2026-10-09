from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.models import MediaInfo, Preset, Progress

ProgressCallback = Callable[[Progress], None]


@dataclass(frozen=True)
class DownloadOptions:
    preset: Preset
    dest_dir: Path
    max_duration_sec: int
    max_filesize_bytes: int


class Engine(Protocol):
    name: str

    def can_handle(self, url: str) -> bool: ...

    async def probe(self, url: str) -> MediaInfo: ...

    async def download(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> list[Path]: ...


def is_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))

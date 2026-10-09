import pytest

from app.engines.base import DownloadOptions
from app.engines.direct import DirectEngine
from app.engines.ytdlp import YtDlpEngine
from app.models import MediaKind, Preset

pytestmark = pytest.mark.network


async def test_ytdlp_probes_public_test_video():
    info = await YtDlpEngine().probe("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    assert info.kind is MediaKind.SINGLE
    assert info.title == "Me at the zoo"


async def test_direct_downloads_raw_file(tmp_path):
    opts = DownloadOptions(Preset.BEST, tmp_path, max_duration_sec=10, max_filesize_bytes=5_000_000)
    [path] = await DirectEngine().download(
        "https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md", opts, lambda p: None
    )
    assert path.stat().st_size > 0

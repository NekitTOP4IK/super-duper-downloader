import pytest
from yt_dlp.utils import DownloadError, GeoRestrictedError, UnsupportedError

from app.core.config import Settings
from app.core.errors import EngineError, ErrorCode
from app.engines import ytdlp as ytdlp_module
from app.engines.base import DownloadOptions
from app.engines.factory import build_router
from app.engines.ytdlp import (
    YtDlpEngine,
    available_presets,
    format_for,
    info_to_media,
    map_ytdlp_error,
)
from app.models import MediaKind, Preset

B, P1080, P720, P480, A = Preset.BEST, Preset.P1080, Preset.P720, Preset.P480, Preset.AUDIO


def test_format_for():
    assert format_for(P720) == "bv*[height<=720]+ba/b[height<=720]"
    assert format_for(A) == "ba/b"
    assert format_for(B) == "bv*+ba/b"


@pytest.mark.parametrize(
    "info, expected",
    [
        (
            {"formats": [{"vcodec": "avc1", "height": 1080}, {"vcodec": "none"}]},
            [B, P1080, P720, P480, A],
        ),
        ({"formats": [{"vcodec": "avc1", "height": 480}]}, [B, P480, A]),
        ({"formats": [{"vcodec": "none", "acodec": "opus"}]}, [A]),
        ({"vcodec": None, "ext": "mp4"}, [B, A]),
    ],
)
def test_available_presets(info, expected):
    assert available_presets(info) == expected


def test_info_to_media_single():
    info = {
        "title": "T",
        "duration": 12.5,
        "uploader": "U",
        "thumbnails": [{"url": "https://i.example/s.jpg"}, {"url": "https://i.example/l.jpg"}],
        "formats": [{"vcodec": "avc1", "height": 720}],
    }
    media = info_to_media("https://v.example", info, 50)
    assert media.kind is MediaKind.SINGLE
    assert (media.title, media.duration, media.uploader) == ("T", 12.5, "U")
    assert media.thumbnail == "https://i.example/l.jpg"
    assert media.presets == [B, P720, P480, A]


def test_info_to_media_playlist_with_flat_entries():
    info = {
        "_type": "playlist",
        "title": "PL",
        "playlist_count": 120,
        "entries": [
            {"url": "https://www.youtube.com/watch?v=a", "title": "A"},
            {"url": "b", "webpage_url": "https://site.example/b", "title": "B"},
            {"url": "c"},
            None,
        ],
    }
    media = info_to_media("https://pl.example", info, 50)
    assert media.kind is MediaKind.PLAYLIST
    assert media.count == 120
    assert [e.url for e in media.entries] == [
        "https://www.youtube.com/watch?v=a",
        "https://site.example/b",
    ]


def test_info_to_media_playlist_respects_limit():
    entries = [{"url": f"https://v.example/{i}"} for i in range(5)]
    media = info_to_media("https://pl.example", {"_type": "playlist", "entries": entries}, 2)
    assert len(media.entries) == 2
    assert media.count == 5


@pytest.mark.parametrize(
    "message, code",
    [
        (
            "ERROR: [youtube] x: Sign in to confirm you’re not a bot. Use --cookies",
            ErrorCode.BLOCKED,
        ),
        (
            "ERROR: [youtube] x: Private video. Sign in if you've been granted access",
            ErrorCode.PRIVATE,
        ),
        ("ERROR: [youtube] x: Sign in to confirm your age", ErrorCode.PRIVATE),
        (
            "ERROR: [instagram] x: Requested content is not available, rate-limit reached or login required",
            ErrorCode.BLOCKED,
        ),
        ("ERROR: [generic] Unsupported URL: https://example.com", ErrorCode.UNSUPPORTED),
        ("ERROR: Unable to download webpage: <urlopen error timed out>", ErrorCode.NETWORK),
        ("ERROR: [youtube] x: Video unavailable", ErrorCode.EXTRACTION_FAILED),
    ],
)
def test_map_ytdlp_error_by_message(message, code):
    assert map_ytdlp_error(DownloadError(message)).code is code


def test_map_ytdlp_error_by_exception_type():
    geo = GeoRestrictedError("blocked here")
    wrapped = DownloadError("ERROR: whatever", exc_info=(type(geo), geo, None))
    assert map_ytdlp_error(wrapped).code is ErrorCode.GEO_BLOCKED
    assert map_ytdlp_error(UnsupportedError("https://example.com")).code is ErrorCode.UNSUPPORTED


def test_map_ytdlp_error_cleans_message():
    err = map_ytdlp_error(DownloadError("\x1b[0;31mERROR:\x1b[0m [youtube] x: Video unavailable"))
    assert err.message == "[youtube] x: Video unavailable"


class FakeYDL:
    behaviour = None

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def extract_info(self, url, download):
        return FakeYDL.behaviour(self.opts)


@pytest.fixture
def fake_ydl(monkeypatch):
    monkeypatch.setattr(ytdlp_module, "YoutubeDL", FakeYDL)
    return FakeYDL


@pytest.fixture
def opts(tmp_path):
    return DownloadOptions(Preset.P720, tmp_path, max_duration_sec=100, max_filesize_bytes=1000)


async def test_download_returns_files_and_reports_progress(fake_ydl, opts):
    def behaviour(ydl_opts):
        ydl_opts["progress_hooks"][0](
            {
                "status": "downloading",
                "downloaded_bytes": 50,
                "total_bytes": 100,
                "speed": 10.0,
                "eta": 5,
            }
        )
        path = opts.dest_dir / "clip [id].mp4"
        path.write_bytes(b"x")
        return {"requested_downloads": [{"filepath": str(path)}]}

    fake_ydl.behaviour = behaviour
    progress = []
    files = await YtDlpEngine().download("https://v.example", opts, progress.append)
    assert [f.name for f in files] == ["clip [id].mp4"]
    assert progress[0].percent == 50.0


async def test_download_rejects_long_media(fake_ydl, opts):
    def behaviour(ydl_opts):
        assert ydl_opts["match_filter"]({"duration": 999}, incomplete=False) is not None
        return {}

    fake_ydl.behaviour = behaviour
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.TOO_LONG


async def test_download_stops_when_size_limit_exceeded(fake_ydl, opts):
    def behaviour(ydl_opts):
        ydl_opts["progress_hooks"][0]({"status": "downloading", "downloaded_bytes": 5000})
        return {}

    fake_ydl.behaviour = behaviour
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.TOO_LARGE


async def test_download_without_file_reports_size_or_failure(fake_ydl, opts):
    fake_ydl.behaviour = lambda ydl_opts: {"filesize_approx": 10_000}
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.TOO_LARGE

    fake_ydl.behaviour = lambda ydl_opts: {}
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.EXTRACTION_FAILED


async def test_download_maps_ytdlp_errors(fake_ydl, opts):
    def behaviour(ydl_opts):
        raise DownloadError("ERROR: [youtube] x: Sign in to confirm you’re not a bot")

    fake_ydl.behaviour = behaviour
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.BLOCKED


def test_build_router_engine_order():
    router = build_router(Settings(_env_file=None))
    assert [engine.name for engine in router.engines] == ["ytdlp", "cobalt", "direct"]

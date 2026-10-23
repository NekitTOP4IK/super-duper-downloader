import pytest
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, GeoRestrictedError, UnsupportedError

from app.core.config import Settings
from app.core.errors import EngineError, ErrorCode
from app.engines import ytdlp as ytdlp_module
from app.engines.base import DownloadOptions
from app.engines.factory import build_router
from app.engines.ytdlp import (
    FORMAT_SORT,
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


def _format(format_id, vcodec, acodec, height, ext):
    return {
        "format_id": format_id,
        "url": f"https://cdn.example/{format_id}",
        "vcodec": vcodec,
        "acodec": acodec,
        "height": height,
        "ext": ext,
        "protocol": "https",
    }


_FORMATS = [
    _format("av1-2160", "av01.0.12M.08", "none", 2160, "mp4"),
    _format("vp9-2160", "vp9", "none", 2160, "webm"),
    _format("av1-1080", "av01.0.08M.08", "none", 1080, "mp4"),
    _format("vp9-1080", "vp9", "none", 1080, "webm"),
    _format("avc-1080", "avc1.640028", "none", 1080, "mp4"),
    _format("opus", "none", "opus", None, "webm"),
    _format("aac", "none", "mp4a.40.2", None, "m4a"),
]


@pytest.mark.parametrize(
    "preset, expected",
    [(B, "vp9-2160+aac"), (P1080, "avc-1080+aac"), (A, "aac")],
)
def test_format_sort_prefers_compatible_codecs_without_losing_resolution(preset, expected):
    ydl = YoutubeDL({"quiet": True, "format": format_for(preset), "format_sort": FORMAT_SORT})
    info = ydl.process_ie_result(
        {
            "id": "x",
            "title": "t",
            "formats": [dict(f) for f in _FORMATS],
            "extractor": "t",
            "extractor_key": "T",
            "webpage_url": "https://site.example/x",
        },
        download=False,
    )
    assert info["format_id"] == expected


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
        ("ERROR: [youtube] x: Video unavailable", ErrorCode.UNAVAILABLE),
        (
            "ERROR: [youtube:tab] x: YouTube said: The playlist does not exist.",
            ErrorCode.UNAVAILABLE,
        ),
        ("ERROR: [twitter] x: This content is no longer available.", ErrorCode.UNAVAILABLE),
        ("ERROR: [generic] Unable to download webpage: HTTP Error 404", ErrorCode.UNAVAILABLE),
        (
            "ERROR: [youtube] x: This content isn't available, try again later. The current"
            " session has been rate-limited by YouTube for up to an hour.",
            ErrorCode.BLOCKED,
        ),
        (
            "ERROR: [youtube] x: Video unavailable. YouTube is requiring a captcha challenge",
            ErrorCode.BLOCKED,
        ),
        ("ERROR: [x] something odd happened", ErrorCode.EXTRACTION_FAILED),
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


def _stream(format_id, done, total, speed=None):
    return {
        "status": "downloading",
        "downloaded_bytes": done,
        "total_bytes": total,
        "speed": speed,
        "info_dict": {"format_id": format_id},
    }


async def test_download_progress_spans_video_and_audio(fake_ydl, opts):
    def behaviour(ydl_opts):
        chosen = {
            "requested_formats": [
                {"format_id": "v", "filesize": 600},
                {"format_id": "a", "filesize_approx": 300},
            ]
        }
        assert ydl_opts["match_filter"](chosen, incomplete=False) is None
        hook = ydl_opts["progress_hooks"][0]
        hook(_stream("v", 300, 600, speed=100.0))
        hook(_stream("v", 600, 600))
        hook(_stream("a", 150, 300))
        hook(_stream("a", 300, 300))
        path = opts.dest_dir / "clip.mp4"
        path.write_bytes(b"x")
        return {"requested_downloads": [{"filepath": str(path)}]}

    fake_ydl.behaviour = behaviour
    progress = []
    await YtDlpEngine().download("https://v.example", opts, progress.append)
    assert [p.percent for p in progress] == [33.3, 66.7, 83.3, 100.0]
    assert {p.total for p in progress} == {900}
    assert [p.downloaded for p in progress] == [300, 600, 750, 900]
    assert progress[0].eta == 6.0


async def test_download_size_limit_counts_all_streams(fake_ydl, opts):
    def behaviour(ydl_opts):
        ydl_opts["progress_hooks"][0](_stream("v", 700, 700))
        ydl_opts["progress_hooks"][0](_stream("a", 400, 400))
        return {}

    fake_ydl.behaviour = behaviour
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://v.example", opts, lambda p: None)
    assert info.value.code is ErrorCode.TOO_LARGE


async def test_download_percent_never_exceeds_100(fake_ydl, opts):
    def behaviour(ydl_opts):
        ydl_opts["progress_hooks"][0](
            {"status": "downloading", "downloaded_bytes": 900, "total_bytes_estimate": 800}
        )
        return {}

    fake_ydl.behaviour = behaviour
    progress = []
    with pytest.raises(EngineError):
        await YtDlpEngine().download("https://v.example", opts, progress.append)
    assert progress[0].percent == 100.0


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

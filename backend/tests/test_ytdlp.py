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
    MERGE_FORMAT,
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


def _select(formats, **params):
    with YoutubeDL({"quiet": True, **params}) as ydl:
        return ydl.process_ie_result(
            {
                "id": "x",
                "title": "t",
                "formats": [dict(f) for f in formats],
                "extractor": "t",
                "extractor_key": "T",
                "webpage_url": "https://site.example/x",
            },
            download=False,
        )


@pytest.mark.parametrize(
    "preset, expected",
    [(B, "vp9-2160+aac"), (P1080, "avc-1080+aac"), (A, "aac")],
)
def test_format_sort_prefers_compatible_codecs_without_losing_resolution(preset, expected):
    info = _select(_FORMATS, format=format_for(preset), format_sort=FORMAT_SORT)
    assert info["format_id"] == expected


@pytest.mark.parametrize(
    "video, audio, expected",
    [
        (("avc1.64001F", "mp4"), (None, "mp4"), "mp4"),
        (("vp09.00.50.08", "webm"), ("mp4a.40.2", "m4a"), "mp4"),
        (("vp9", "webm"), ("opus", "webm"), "webm"),
    ],
)
def test_merged_streams_land_in_a_common_container(video, audio, expected):
    formats = [
        _format("v", video[0], "none", 720, video[1]),
        _format("a", "none", audio[0], None, audio[1]),
    ]
    info = _select(formats, format=format_for(B), merge_output_format=MERGE_FORMAT)
    assert info["ext"] == expected


@pytest.mark.parametrize(
    "info, expected",
    [
        (
            {"formats": [{"vcodec": "avc1", "height": 1080}, {"vcodec": "none"}]},
            [B, P1080, P720, P480, A],
        ),
        ({"formats": [{"vcodec": "avc1", "height": 480}]}, [B, P480, A]),
        ({"formats": [{"vcodec": "avc1", "acodec": "none", "height": 480}]}, [B, P480]),
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


def test_info_to_media_post_with_several_videos_is_one_item():
    info = {
        "_type": "playlist",
        "title": "Post",
        "uploader": "U",
        "entries": [
            {
                "url": "https://cdn.example/1.mp4",
                "thumbnail": "https://i.example/1.jpg",
                "formats": [{"vcodec": "avc1", "height": 720}],
            },
            {"url": "https://cdn.example/2.mp4", "formats": [{"vcodec": "avc1", "height": 1080}]},
        ],
    }
    media = info_to_media("https://site.example/p/1", info, 50)
    assert media.kind is MediaKind.SINGLE
    assert (media.title, media.uploader, media.count) == ("Post", "U", 2)
    assert media.thumbnail == "https://i.example/1.jpg"
    assert media.presets == [B, P1080, P720, P480, A]
    assert media.entries == []


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
        (
            "ERROR: [TikTok] 1: Your IP address is blocked from accessing this post",
            ErrorCode.GEO_BLOCKED,
        ),
        (
            "ERROR: [instagram:story] 1: You need to log in to access this content. Use"
            " --cookies-from-browser or --cookies for the authentication.",
            ErrorCode.PRIVATE,
        ),
        (
            "ERROR: [facebook] 1: This video is only available for registered users. Use"
            " --cookies-from-browser or --cookies for the authentication.",
            ErrorCode.PRIVATE,
        ),
        (
            "ERROR: [Reddit] 1: Account authentication is required. Use --cookies-from-browser",
            ErrorCode.BLOCKED,
        ),
        (
            "ERROR: [vimeo] 1: The web client only works when logged-in. Use --cookies",
            ErrorCode.PRIVATE,
        ),
        ("ERROR: [x] 1: You have to be logged in to get your history", ErrorCode.PRIVATE),
        (
            "ERROR: [Douyin] 1: Fresh cookies (not necessarily logged in) are needed",
            ErrorCode.EXTRACTION_FAILED,
        ),
        (
            "ERROR: [Instagram] 1: Instagram sent an empty media response. Check if this post is"
            " accessible in your browser without being logged-in.",
            ErrorCode.EXTRACTION_FAILED,
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


def test_ytdlp_can_impersonate_a_browser():
    # TikTok and others answer clients that do not look like a browser with a bot challenge.
    from yt_dlp.networking.impersonate import ImpersonateTarget

    with YoutubeDL({"quiet": True}) as ydl:
        assert ydl._impersonate_target_available(ImpersonateTarget())


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


async def test_download_progress_accepts_estimated_sizes(fake_ydl, opts):
    def behaviour(ydl_opts):
        chosen = {
            "requested_formats": [
                {"format_id": "v", "filesize_approx": 600.5},
                {"format_id": "a", "filesize_approx": 300.25},
            ]
        }
        ydl_opts["match_filter"](chosen, incomplete=False)
        ydl_opts["progress_hooks"][0]({**_stream("v", 300, None), "total_bytes_estimate": 600.75})
        path = opts.dest_dir / "clip.mp4"
        path.write_bytes(b"x")
        return {"requested_downloads": [{"filepath": str(path)}]}

    fake_ydl.behaviour = behaviour
    progress = []
    await YtDlpEngine().download("https://v.example", opts, progress.append)
    assert progress[0].total == 900
    assert progress[0].downloaded == 300


async def test_download_percent_does_not_go_back_when_estimate_grows(fake_ydl, opts):
    def behaviour(ydl_opts):
        hook = ydl_opts["progress_hooks"][0]
        hook({**_stream("v", 400, None), "total_bytes_estimate": 800})
        hook({**_stream("v", 450, None), "total_bytes_estimate": 1000})
        hook({**_stream("v", 900, None), "total_bytes_estimate": 1000})
        path = opts.dest_dir / "clip.mp4"
        path.write_bytes(b"x")
        return {"requested_downloads": [{"filepath": str(path)}]}

    fake_ydl.behaviour = behaviour
    progress = []
    await YtDlpEngine().download("https://v.example", opts, progress.append)
    assert [p.percent for p in progress] == [50.0, 50.0, 90.0]


def _item(position, count):
    return {
        "requested_formats": [{"format_id": "f"}],
        "playlist_autonumber": position,
        "n_entries": count,
    }


async def test_download_of_a_post_returns_every_item(fake_ydl, opts):
    def behaviour(ydl_opts):
        hook = ydl_opts["progress_hooks"][0]
        entries = []
        for position in (1, 2):
            ydl_opts["match_filter"](_item(position, 2), incomplete=False)
            hook(_stream("f", 100, 200))
            hook(_stream("f", 200, 200))
            path = opts.dest_dir / f"{position}.mp4"
            path.write_bytes(b"x")
            entries.append({"requested_downloads": [{"filepath": str(path)}]})
        return {"_type": "playlist", "entries": entries}

    fake_ydl.behaviour = behaviour
    progress = []
    files = await YtDlpEngine().download("https://site.example/p/1", opts, progress.append)
    assert [f.name for f in files] == ["1.mp4", "2.mp4"]
    assert [p.percent for p in progress] == [25.0, 50.0, 75.0, 100.0]
    assert [p.downloaded for p in progress] == [100, 200, 300, 400]


async def test_download_size_limit_counts_every_item_of_a_post(fake_ydl, opts):
    def behaviour(ydl_opts):
        for position in (1, 2):
            ydl_opts["match_filter"](_item(position, 2), incomplete=False)
            ydl_opts["progress_hooks"][0](_stream("f", 600, 600))
        return {}

    fake_ydl.behaviour = behaviour
    with pytest.raises(EngineError) as info:
        await YtDlpEngine().download("https://site.example/p/1", opts, lambda p: None)
    assert info.value.code is ErrorCode.TOO_LARGE


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


async def test_file_names_fit_the_filesystem_limit(fake_ydl, opts):
    used = {}
    fake_ydl.behaviour = lambda ydl_opts: used.update(ydl_opts) or {}
    with pytest.raises(EngineError):
        await YtDlpEngine().download("https://cdn.example/x.mp4", opts, lambda p: None)
    with YoutubeDL({"outtmpl": used["outtmpl"]}) as ydl:
        name = ydl.prepare_filename({"id": "i" * 300, "title": "т" * 300, "ext": "mp4"})
    assert len(name.encode()) <= 255

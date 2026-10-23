import asyncio
import re
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import GeoRestrictedError, UnsupportedError

from app.core import netguard
from app.core.errors import EngineError, ErrorCode
from app.engines.base import DownloadOptions, ProgressCallback, is_http_url
from app.models import MediaInfo, MediaKind, PlaylistEntry, Preset, Progress

PRESET_FORMATS = {
    Preset.BEST: "bv*+ba/b",
    Preset.P1080: "bv*[height<=1080]+ba/b[height<=1080]",
    Preset.P720: "bv*[height<=720]+ba/b[height<=720]",
    Preset.P480: "bv*[height<=480]+ba/b[height<=480]",
    Preset.AUDIO: "ba/b",
}
_HEIGHT_PRESETS = ((Preset.P1080, 1080), (Preset.P720, 720), (Preset.P480, 480))
# Within one resolution prefer H.264 + AAC: AV1 and Opus still fail on older phones and TVs.
FORMAT_SORT = ["res", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"]

_ERROR_PATTERNS = (
    (ErrorCode.FORBIDDEN, (netguard.BLOCKED_MESSAGE,)),
    (
        ErrorCode.BLOCKED,
        (
            "not a bot",
            "http error 403",
            "http error 429",
            "too many requests",
            "rate-limit",
            "rate limit",
            "captcha",
        ),
    ),
    (
        ErrorCode.PRIVATE,
        (
            "private video",
            "video is private",
            "confirm your age",
            "age-restricted",
            "login required",
            "members-only",
            "join this channel",
        ),
    ),
    (
        ErrorCode.GEO_BLOCKED,
        (
            "not available in your country",
            "geo restriction",
            "geo-restricted",
            "ip address is blocked",
        ),
    ),
    (
        ErrorCode.UNAVAILABLE,
        (
            "video unavailable",
            "does not exist",
            "has been removed",
            "no longer available",
            "http error 404",
        ),
    ),
    (ErrorCode.UNSUPPORTED, ("unsupported url",)),
    (
        ErrorCode.NETWORK,
        (
            "timed out",
            "connection reset",
            "connection refused",
            "temporary failure in name resolution",
            "name or service not known",
            "network is unreachable",
        ),
    ),
)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def format_for(preset: Preset) -> str:
    return PRESET_FORMATS[preset]


def available_presets(info: dict[str, Any]) -> list[Preset]:
    formats = info.get("formats") or [info]
    video = [f for f in formats if f.get("vcodec") != "none"]
    if not video:
        return [Preset.AUDIO]
    max_height = max((f.get("height") or 0 for f in video), default=0)
    heights = [preset for preset, height in _HEIGHT_PRESETS if max_height >= height]
    return [Preset.BEST, *heights, Preset.AUDIO]


def info_to_media(url: str, info: dict[str, Any], playlist_limit: int) -> MediaInfo:
    if info.get("_type") in ("playlist", "multi_video"):
        entries = [entry for entry in map(_entry, info.get("entries") or []) if entry]
        return MediaInfo(
            kind=MediaKind.PLAYLIST,
            url=url,
            title=info.get("title"),
            thumbnail=_thumbnail(info),
            uploader=info.get("uploader") or info.get("channel"),
            count=info.get("playlist_count") or len(entries),
            entries=entries[:playlist_limit],
        )
    return MediaInfo(
        kind=MediaKind.SINGLE,
        url=url,
        title=info.get("title"),
        thumbnail=_thumbnail(info),
        duration=info.get("duration"),
        uploader=info.get("uploader") or info.get("channel"),
        presets=available_presets(info),
    )


def map_ytdlp_error(exc: BaseException) -> EngineError:
    exc_info = getattr(exc, "exc_info", None)
    inner = exc_info[1] if exc_info else None
    for candidate in (exc, inner):
        if isinstance(candidate, GeoRestrictedError):
            return EngineError(ErrorCode.GEO_BLOCKED, _clean(str(exc)))
        if isinstance(candidate, UnsupportedError):
            return EngineError(ErrorCode.UNSUPPORTED, _clean(str(exc)))
    message = _clean(str(exc))
    lowered = message.lower()
    for code, patterns in _ERROR_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            # The raw text names internal hosts and addresses, which users should not see.
            text = netguard.BLOCKED_MESSAGE if code is ErrorCode.FORBIDDEN else message
            return EngineError(code, text)
    return EngineError(ErrorCode.EXTRACTION_FAILED, message)


class YtDlpEngine:
    name = "ytdlp"

    def __init__(self, *, proxy_url: str = "", playlist_limit: int = 50) -> None:
        self._proxy_url = proxy_url
        self._playlist_limit = playlist_limit

    def can_handle(self, url: str) -> bool:
        return is_http_url(url)

    async def probe(self, url: str) -> MediaInfo:
        with netguard.untrusted():
            return await asyncio.to_thread(self._probe_sync, url)

    async def download(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> list[Path]:
        with netguard.untrusted():
            return await asyncio.to_thread(self._download_sync, url, opts, on_progress)

    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }
        if self._proxy_url:
            opts["proxy"] = self._proxy_url
        return opts

    def _probe_sync(self, url: str) -> MediaInfo:
        opts = {
            **self._base_opts(),
            "extract_flat": "in_playlist",
            "playlist_items": f"1-{self._playlist_limit}",
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise map_ytdlp_error(exc) from exc
        if not info:
            raise EngineError(ErrorCode.EXTRACTION_FAILED, "yt-dlp returned no metadata")
        return info_to_media(url, info, self._playlist_limit)

    def _download_sync(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> list[Path]:
        violations: list[ErrorCode] = []
        streams = _Streams()

        def match_filter(info: dict[str, Any], *, incomplete: bool) -> str | None:
            duration = info.get("duration")
            if duration and duration > opts.max_duration_sec:
                violations.append(ErrorCode.TOO_LONG)
                return "duration limit exceeded"
            if not incomplete:
                # The last call, made once formats are chosen and before any of them downloads.
                streams.plan(info)
            return None

        def progress_hook(status: dict[str, Any]) -> None:
            if status.get("status") != "downloading":
                return
            progress = streams.update(status)
            if (progress.downloaded or 0) > opts.max_filesize_bytes:
                violations.append(ErrorCode.TOO_LARGE)
                raise EngineError(ErrorCode.TOO_LARGE)
            on_progress(progress)

        def postprocessor_hook(status: dict[str, Any]) -> None:
            if status.get("status") == "started":
                on_progress(Progress(stage="processing"))

        ydl_opts = {
            **self._base_opts(),
            "format": format_for(opts.preset),
            "format_sort": FORMAT_SORT,
            "merge_output_format": "mp4/mkv",
            "outtmpl": {"default": "%(title).150B [%(id)s].%(ext)s"},
            "paths": {"home": str(opts.dest_dir), "temp": str(opts.dest_dir / ".part")},
            "windowsfilenames": True,
            "max_filesize": opts.max_filesize_bytes,
            "match_filter": match_filter,
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True) or {}
        except Exception as exc:
            if violations:
                raise EngineError(violations[0]) from exc
            raise map_ytdlp_error(exc) from exc
        if violations:
            raise EngineError(violations[0])
        files = [
            Path(item["filepath"])
            for item in info.get("requested_downloads") or []
            if item.get("filepath")
        ]
        existing = [path for path in files if path.exists()]
        if existing:
            return existing
        size = info.get("filesize") or info.get("filesize_approx")
        if size and size > opts.max_filesize_bytes:
            raise EngineError(ErrorCode.TOO_LARGE)
        raise EngineError(ErrorCode.EXTRACTION_FAILED, "yt-dlp finished without producing a file")


class _Streams:
    """Adds up the streams of one download: yt-dlp fetches video and audio one after another."""

    def __init__(self) -> None:
        self._planned: dict[str, int | None] = {}
        self._seen: dict[str, tuple[int, int | None]] = {}
        self._percent = 0.0

    def plan(self, info: dict[str, Any]) -> None:
        self._planned = {
            str(fmt.get("format_id")): _size(fmt.get("filesize") or fmt.get("filesize_approx"))
            for fmt in info.get("requested_formats") or [info]
        }
        self._seen = {}
        self._percent = 0.0

    def update(self, status: dict[str, Any]) -> Progress:
        current = str((status.get("info_dict") or {}).get("format_id"))
        self._seen[current] = (
            _size(status.get("downloaded_bytes")) or 0,
            _size(status.get("total_bytes") or status.get("total_bytes_estimate")),
        )
        sizes = [size for _, size in self._seen.values()]
        sizes += [size for fmt, size in self._planned.items() if fmt not in self._seen]
        done = sum(downloaded for downloaded, _ in self._seen.values())
        total = sum(sizes) if all(sizes) else None
        speed = status.get("speed")
        if total:
            # Fragmented streams only have a size estimate, which shifts as fragments arrive.
            self._percent = max(self._percent, min(100.0, round(done * 100 / total, 1)))
        return Progress(
            percent=self._percent if total else None,
            speed=speed,
            eta=max(0, total - done) / speed if total and speed else status.get("eta"),
            downloaded=done,
            total=total,
        )


def _size(value: float | None) -> int | None:
    # Estimates for HLS and approximate format sizes come as floats.
    return int(value) if value else None


def _entry(entry: dict[str, Any] | None) -> PlaylistEntry | None:
    if not entry:
        return None
    url = next(
        (c for c in (entry.get("url"), entry.get("webpage_url")) if c and is_http_url(c)), None
    )
    if url is None:
        return None
    return PlaylistEntry(url=url, title=entry.get("title"), duration=entry.get("duration"))


def _thumbnail(info: dict[str, Any]) -> str | None:
    if info.get("thumbnail"):
        return info["thumbnail"]
    urls = [thumb["url"] for thumb in info.get("thumbnails") or [] if thumb.get("url")]
    return urls[-1] if urls else None


def _clean(message: str) -> str:
    return _ANSI.sub("", message).removeprefix("ERROR: ").strip()[:300]

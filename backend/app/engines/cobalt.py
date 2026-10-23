from contextlib import nullcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core import netguard
from app.core.errors import EngineError, ErrorCode
from app.engines.base import DownloadOptions, ProgressCallback, is_http_url
from app.engines.http_download import stream_to_file
from app.models import MediaInfo, MediaKind, Preset

_QUALITY = {
    Preset.BEST: "max",
    Preset.P1080: "1080",
    Preset.P720: "720",
    Preset.P480: "480",
    Preset.AUDIO: "max",
}

_EXACT_CODES = {
    "service.unsupported": ErrorCode.UNSUPPORTED,
    "service.disabled": ErrorCode.UNSUPPORTED,
    "service.audio_not_supported": ErrorCode.UNSUPPORTED,
    "link.invalid": ErrorCode.UNSUPPORTED,
    "link.unsupported": ErrorCode.UNSUPPORTED,
    "content.video.private": ErrorCode.PRIVATE,
    "content.post.private": ErrorCode.PRIVATE,
    "content.video.age": ErrorCode.PRIVATE,
    "content.post.age": ErrorCode.PRIVATE,
    "content.paid": ErrorCode.PRIVATE,
    "youtube.login": ErrorCode.PRIVATE,
    "content.video.region": ErrorCode.GEO_BLOCKED,
    "content.region": ErrorCode.GEO_BLOCKED,
    "content.too_long": ErrorCode.TOO_LONG,
    "content.video.unavailable": ErrorCode.UNAVAILABLE,
    "content.post.unavailable": ErrorCode.UNAVAILABLE,
    "unreachable": ErrorCode.NETWORK,
    "timed_out": ErrorCode.NETWORK,
    "rate_exceeded": ErrorCode.BLOCKED,
    "capacity": ErrorCode.BLOCKED,
    "fetch.rate": ErrorCode.BLOCKED,
}
_PREFIX_CODES = (("auth.", ErrorCode.BLOCKED), ("youtube.", ErrorCode.BLOCKED))


def map_cobalt_error(code: str) -> EngineError:
    key = code.removeprefix("error.api.")
    mapped = _EXACT_CODES.get(key) or next(
        (value for prefix, value in _PREFIX_CODES if key.startswith(prefix)),
        ErrorCode.EXTRACTION_FAILED,
    )
    return EngineError(mapped, f"cobalt: {key or 'unknown error'}")


class CobaltEngine:
    name = "cobalt"

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=True, timeout=self._timeout, transport=self._transport
        )

    def can_handle(self, url: str) -> bool:
        return is_http_url(url)

    async def probe(self, url: str) -> MediaInfo:
        async with self._client() as client:
            data = await self._resolve(client, url, Preset.BEST)
        if data["status"] == "picker":
            return MediaInfo(kind=MediaKind.SINGLE, url=url, presets=[Preset.BEST])
        filename = data.get("filename")
        return MediaInfo(
            kind=MediaKind.SINGLE,
            url=url,
            title=Path(filename).stem if filename else None,
            presets=list(Preset),
        )

    async def download(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> list[Path]:
        async with self._client() as client:
            data = await self._resolve(client, url, opts.preset)
            if data["status"] != "picker":
                return [
                    await self._fetch(
                        client, data["url"], opts, on_progress, filename=data.get("filename")
                    )
                ]
            items = [item for item in data.get("picker") or [] if item.get("url")]
            if not items:
                raise EngineError(ErrorCode.EXTRACTION_FAILED, "cobalt returned an empty picker")
            return [
                await self._fetch(
                    client, item["url"], opts, on_progress, name_prefix=f"{index:02d}_"
                )
                for index, item in enumerate(items, start=1)
            ]

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        opts: DownloadOptions,
        on_progress: ProgressCallback,
        *,
        filename: str | None = None,
        name_prefix: str = "",
    ) -> Path:
        # Tunnels are served by cobalt itself. Redirect and picker URLs come from the site's
        # API, so they are fetched like any user-supplied URL.
        own = urlsplit(url)[:2] == urlsplit(self._base_url)[:2]
        with nullcontext() if own else netguard.untrusted():
            return await stream_to_file(
                client,
                url,
                opts.dest_dir,
                max_bytes=opts.max_filesize_bytes,
                on_progress=on_progress,
                filename=filename,
                name_prefix=name_prefix,
            )

    async def _resolve(self, client: httpx.AsyncClient, url: str, preset: Preset) -> dict[str, Any]:
        body = {
            "url": url,
            "videoQuality": _QUALITY[preset],
            "downloadMode": "audio" if preset is Preset.AUDIO else "auto",
            "audioFormat": "best",
            "filenameStyle": "basic",
        }
        try:
            response = await client.post(
                f"{self._base_url}/", json=body, headers={"Accept": "application/json"}
            )
        except httpx.TransportError as exc:
            raise EngineError(ErrorCode.NETWORK, f"cobalt unreachable: {exc}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            code = ErrorCode.NETWORK if response.status_code >= 500 else ErrorCode.EXTRACTION_FAILED
            raise EngineError(code, f"cobalt returned HTTP {response.status_code}") from exc
        status = data.get("status")
        if status == "error":
            raise map_cobalt_error((data.get("error") or {}).get("code", ""))
        if status not in ("tunnel", "redirect", "picker"):
            raise EngineError(ErrorCode.EXTRACTION_FAILED, f"unsupported cobalt response: {status}")
        return data

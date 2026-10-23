from pathlib import Path

import httpx

from app.engines.base import DownloadOptions, ProgressCallback, is_http_url
from app.engines.http_download import (
    USER_AGENT,
    ensure_ok,
    filename_from_response,
    stream_to_file,
    transport_error,
)
from app.models import MediaInfo, MediaKind, Preset


class DirectEngine:
    name = "direct"

    def __init__(
        self,
        *,
        proxy_url: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._proxy_url = proxy_url
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            follow_redirects=True,
            timeout=self._timeout,
            proxy=self._proxy_url or None,
            transport=self._transport,
            headers={"User-Agent": USER_AGENT},
        )

    def can_handle(self, url: str) -> bool:
        return is_http_url(url)

    async def probe(self, url: str) -> MediaInfo:
        try:
            async with self._client() as client, client.stream("GET", url) as response:
                ensure_ok(response, reject_pages=True)
                name = filename_from_response(response)
        except httpx.TransportError as exc:
            raise transport_error(exc) from exc
        return MediaInfo(kind=MediaKind.SINGLE, url=url, title=name, presets=[Preset.BEST])

    async def download(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> list[Path]:
        async with self._client() as client:
            path = await stream_to_file(
                client,
                url,
                opts.dest_dir,
                max_bytes=opts.max_filesize_bytes,
                on_progress=on_progress,
                reject_pages=True,
            )
        return [path]

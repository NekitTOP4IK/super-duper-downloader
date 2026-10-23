import re
from email.message import Message
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from app.core import netguard
from app.core.errors import EngineError, ErrorCode
from app.engines.base import ProgressCallback
from app.models import Progress

# Sites such as Wikimedia reject anonymous or browser-imitating clients from servers and
# ask for a descriptive agent with a contact link instead.
USER_AGENT = "super-duper-downloader/0.1 (+https://github.com/NekitTOP4IK/super-duper-downloader)"
PAGE_TYPES = frozenset({"text/html", "application/xhtml+xml"})
MAX_NAME_LENGTH = 150

_UNSAFE_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def safe_filename(name: str, fallback: str = "download") -> str:
    cleaned = _UNSAFE_CHARS.sub("_", name).strip().strip(".")
    if not cleaned:
        return fallback
    stem, dot, ext = cleaned.rpartition(".")
    if dot and stem and len(ext) <= 10:
        return f"{stem[: MAX_NAME_LENGTH - len(ext) - 1]}.{ext}"
    return cleaned[:MAX_NAME_LENGTH]


def filename_from_response(response: httpx.Response) -> str:
    disposition = response.headers.get("content-disposition")
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        name = message.get_filename()
        if name:
            return safe_filename(name)
    last_segment = urlsplit(str(response.url)).path.rsplit("/", 1)[-1]
    return safe_filename(unquote(last_segment))


def content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";")[0].strip().lower()


def http_error(status: int) -> EngineError:
    if status == 401:
        code = ErrorCode.PRIVATE
    elif status in (403, 429):
        code = ErrorCode.BLOCKED
    elif status in (404, 410):
        code = ErrorCode.UNAVAILABLE
    elif status == 451:
        code = ErrorCode.GEO_BLOCKED
    elif status >= 500:
        code = ErrorCode.NETWORK
    else:
        code = ErrorCode.EXTRACTION_FAILED
    return EngineError(code, f"HTTP {status}")


def ensure_ok(response: httpx.Response, *, reject_pages: bool) -> None:
    if response.status_code >= 400:
        raise http_error(response.status_code)
    if reject_pages and content_type(response) in PAGE_TYPES:
        raise EngineError(ErrorCode.UNSUPPORTED, "URL points to a web page, not a file")


async def stream_to_file(
    client: httpx.AsyncClient,
    url: str,
    dest_dir: Path,
    *,
    max_bytes: int,
    on_progress: ProgressCallback,
    filename: str | None = None,
    name_prefix: str = "",
    reject_pages: bool = False,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    too_large = EngineError(ErrorCode.TOO_LARGE, f"file is larger than {max_bytes} bytes")
    try:
        async with client.stream("GET", url) as response:
            ensure_ok(response, reject_pages=reject_pages)
            exact = _int_header(response, "content-length")
            if exact is not None and exact > max_bytes:
                raise too_large
            total = exact or _int_header(response, "estimated-content-length")
            name = safe_filename(filename) if filename else filename_from_response(response)
            path = dest_dir / f"{name_prefix}{name}"
            done = 0
            with path.open("wb") as fh:
                async for chunk in response.aiter_bytes():
                    done += len(chunk)
                    if done > max_bytes:
                        raise too_large
                    fh.write(chunk)
                    on_progress(
                        Progress(percent=_percent(done, total), downloaded=done, total=total)
                    )
    except httpx.TransportError as exc:
        raise transport_error(exc) from exc
    if done == 0:
        # A cobalt tunnel answers 200 with no body when it could not fetch the media.
        path.unlink()
        raise EngineError(ErrorCode.EXTRACTION_FAILED, "the server sent an empty file")
    return path


def transport_error(exc: httpx.TransportError) -> EngineError:
    if netguard.is_blocked(exc):
        return EngineError(ErrorCode.FORBIDDEN, netguard.BLOCKED_MESSAGE)
    return EngineError(ErrorCode.NETWORK, f"network error: {exc}")


def _int_header(response: httpx.Response, name: str) -> int | None:
    value = response.headers.get(name, "")
    return int(value) if value.isdigit() else None


def _percent(done: int, total: int | None) -> float | None:
    return round(done * 100 / total, 1) if total else None

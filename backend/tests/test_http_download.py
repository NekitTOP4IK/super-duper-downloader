import httpx
import pytest

from app.core.errors import EngineError, ErrorCode
from app.engines.http_download import safe_filename, stream_to_file


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def fetch(client, url, tmp_path, **kwargs):
    kwargs.setdefault("max_bytes", 100)
    kwargs.setdefault("on_progress", lambda p: None)
    return await stream_to_file(client, url, tmp_path, **kwargs)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("my video.mp4", "my video.mp4"),
        (r"a/b\c:d.mp4", "a_b_c_d.mp4"),
        ("...", "download"),
        ("", "download"),
        ("x" * 300 + ".mp4", "x" * 146 + ".mp4"),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


async def test_uses_content_disposition_name(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            content=b"abc",
            headers={
                "content-disposition": "attachment; filename*=UTF-8''%D0%B2%D0%B8%D0%B4%D0%B5%D0%BE.mp4"
            },
        )

    progress = []
    async with client_for(handler) as client:
        path = await fetch(client, "https://h.example/x", tmp_path, on_progress=progress.append)
    assert path.name == "видео.mp4"
    assert path.read_bytes() == b"abc"
    assert progress[-1].percent == 100.0


async def test_falls_back_to_url_path_name_with_prefix(tmp_path):
    async with client_for(lambda request: httpx.Response(200, content=b"x")) as client:
        path = await fetch(
            client, "https://h.example/files/report%20v2.pdf", tmp_path, name_prefix="01_"
        )
    assert path.name == "01_report v2.pdf"


async def test_explicit_filename_wins(tmp_path):
    async with client_for(lambda request: httpx.Response(200, content=b"x")) as client:
        path = await fetch(client, "https://h.example/a", tmp_path, filename="clip.mp4")
    assert path.name == "clip.mp4"


async def test_rejects_declared_size_over_limit(tmp_path):
    async with client_for(lambda request: httpx.Response(200, content=b"x" * 200)) as client:
        with pytest.raises(EngineError) as info:
            await fetch(client, "https://h.example/a", tmp_path)
    assert info.value.code is ErrorCode.TOO_LARGE
    assert list(tmp_path.iterdir()) == []


async def test_rejects_streamed_size_over_limit(tmp_path):
    async def chunks():
        for _ in range(3):
            yield b"x" * 60

    async with client_for(lambda request: httpx.Response(200, content=chunks())) as client:
        with pytest.raises(EngineError) as info:
            await fetch(client, "https://h.example/a", tmp_path)
    assert info.value.code is ErrorCode.TOO_LARGE


@pytest.mark.parametrize(
    "status, code",
    [
        (401, ErrorCode.PRIVATE),
        (403, ErrorCode.BLOCKED),
        (429, ErrorCode.BLOCKED),
        (451, ErrorCode.GEO_BLOCKED),
        (404, ErrorCode.UNAVAILABLE),
        (410, ErrorCode.UNAVAILABLE),
        (400, ErrorCode.EXTRACTION_FAILED),
        (503, ErrorCode.NETWORK),
    ],
)
async def test_maps_http_status(tmp_path, status, code):
    async with client_for(lambda request: httpx.Response(status)) as client:
        with pytest.raises(EngineError) as info:
            await fetch(client, "https://h.example/a", tmp_path)
    assert info.value.code is code


async def test_transport_error_is_network(tmp_path):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    async with client_for(handler) as client:
        with pytest.raises(EngineError) as info:
            await fetch(client, "https://h.example/a", tmp_path)
    assert info.value.code is ErrorCode.NETWORK


async def test_rejects_html_pages_when_asked(tmp_path):
    def handler(request):
        return httpx.Response(
            200, content=b"<html>", headers={"content-type": "text/html; charset=utf-8"}
        )

    async with client_for(handler) as client:
        with pytest.raises(EngineError) as info:
            await fetch(client, "https://h.example/a", tmp_path, reject_pages=True)
    assert info.value.code is ErrorCode.UNSUPPORTED

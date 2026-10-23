import httpx
import pytest

from app.core.errors import EngineError, ErrorCode
from app.engines.base import DownloadOptions
from app.engines.direct import DirectEngine
from app.models import MediaKind, Preset


def file_handler(request):
    if request.url.path.endswith(".html"):
        return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})
    return httpx.Response(200, content=b"PDFDATA", headers={"content-type": "application/pdf"})


@pytest.fixture
def engine():
    return DirectEngine(transport=httpx.MockTransport(file_handler))


@pytest.fixture
def opts(tmp_path):
    return DownloadOptions(Preset.BEST, tmp_path, max_duration_sec=10, max_filesize_bytes=1000)


async def test_probe_file(engine):
    info = await engine.probe("https://h.example/docs/manual.pdf")
    assert info.kind is MediaKind.SINGLE
    assert info.title == "manual.pdf"
    assert info.presets == [Preset.BEST]


async def test_probe_rejects_pages(engine):
    with pytest.raises(EngineError) as info:
        await engine.probe("https://h.example/index.html")
    assert info.value.code is ErrorCode.UNSUPPORTED


async def test_download_file(engine, opts):
    [path] = await engine.download("https://h.example/docs/manual.pdf", opts, lambda p: None)
    assert path.read_bytes() == b"PDFDATA"


async def test_download_rejects_pages(engine, opts):
    with pytest.raises(EngineError) as info:
        await engine.download("https://h.example/index.html", opts, lambda p: None)
    assert info.value.code is ErrorCode.UNSUPPORTED


def test_handles_only_http(engine):
    assert engine.can_handle("https://h.example/a")
    assert not engine.can_handle("ftp://h.example/a")


async def test_socks_proxies_are_supported():
    engine = DirectEngine(proxy_url="socks5://127.0.0.1:9")
    with pytest.raises(EngineError) as info:
        await engine.probe("https://example.com/file.zip")
    assert info.value.code is ErrorCode.NETWORK

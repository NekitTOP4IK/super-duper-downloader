import json

import httpx
import pytest

from app.core.errors import EngineError, ErrorCode
from app.engines.base import DownloadOptions
from app.engines.cobalt import CobaltEngine, map_cobalt_error
from app.models import Preset

BASE = "http://cobalt:9000"
TUNNEL = {"status": "tunnel", "url": f"{BASE}/tunnel?id=1", "filename": "clip.mp4"}


def make_engine(resolve, files=None, status=200, seen=None):
    def handler(request):
        if request.method == "POST":
            if seen is not None:
                seen.append(json.loads(request.content))
            return httpx.Response(status, json=resolve)
        return httpx.Response(200, content=(files or {})[request.url.path])

    return CobaltEngine(BASE, transport=httpx.MockTransport(handler))


def opts(tmp_path, preset=Preset.BEST):
    return DownloadOptions(preset, tmp_path, max_duration_sec=100, max_filesize_bytes=1000)


async def test_probe_uses_filename_as_title():
    info = await make_engine(TUNNEL).probe("https://x.com/a/status/1")
    assert info.title == "clip"
    assert info.presets == list(Preset)


async def test_download_tunnel(tmp_path):
    seen = []
    engine = make_engine(TUNNEL, files={"/tunnel": b"VIDEO"}, seen=seen)
    [path] = await engine.download(
        "https://x.com/a/status/1", opts(tmp_path, Preset.P720), lambda p: None
    )
    assert path.name == "clip.mp4"
    assert path.read_bytes() == b"VIDEO"
    assert seen[0]["videoQuality"] == "720"
    assert seen[0]["downloadMode"] == "auto"


async def test_audio_preset_requests_audio_mode(tmp_path):
    seen = []
    engine = make_engine(TUNNEL, files={"/tunnel": b"A"}, seen=seen)
    await engine.download("https://x.com/a", opts(tmp_path, Preset.AUDIO), lambda p: None)
    assert seen[0]["downloadMode"] == "audio"


async def test_download_picker_saves_every_item(tmp_path):
    picker = {
        "status": "picker",
        "picker": [
            {"type": "photo", "url": "https://cdn.example/a.jpg"},
            {"type": "photo", "url": "https://cdn.example/b.jpg"},
        ],
    }
    engine = make_engine(picker, files={"/a.jpg": b"A", "/b.jpg": b"B"})
    paths = await engine.download("https://instagram.com/p/1", opts(tmp_path), lambda p: None)
    assert [p.name for p in paths] == ["01_a.jpg", "02_b.jpg"]


async def test_error_response_is_mapped():
    error = {"status": "error", "error": {"code": "error.api.content.video.private"}}
    with pytest.raises(EngineError) as info:
        await make_engine(error, status=400).probe("https://x.com/a")
    assert info.value.code is ErrorCode.PRIVATE


async def test_non_json_5xx_is_network():
    def handler(request):
        return httpx.Response(502, content=b"<html>bad gateway</html>")

    engine = CobaltEngine(BASE, transport=httpx.MockTransport(handler))
    with pytest.raises(EngineError) as info:
        await engine.probe("https://x.com/a")
    assert info.value.code is ErrorCode.NETWORK


async def test_connection_error_is_network():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(EngineError) as info:
        await CobaltEngine(BASE, transport=httpx.MockTransport(handler)).probe("https://x.com/a")
    assert info.value.code is ErrorCode.NETWORK


@pytest.mark.parametrize(
    "code, expected",
    [
        ("error.api.link.unsupported", ErrorCode.UNSUPPORTED),
        ("error.api.service.unsupported", ErrorCode.UNSUPPORTED),
        ("error.api.content.post.private", ErrorCode.PRIVATE),
        ("error.api.youtube.login", ErrorCode.PRIVATE),
        ("error.api.content.region", ErrorCode.GEO_BLOCKED),
        ("error.api.content.too_long", ErrorCode.TOO_LONG),
        ("error.api.timed_out", ErrorCode.NETWORK),
        ("error.api.fetch.rate", ErrorCode.BLOCKED),
        ("error.api.youtube.decipher", ErrorCode.BLOCKED),
        ("error.api.auth.jwt.missing", ErrorCode.BLOCKED),
        ("error.api.fetch.fail", ErrorCode.EXTRACTION_FAILED),
        ("", ErrorCode.EXTRACTION_FAILED),
    ],
)
def test_map_cobalt_error(code, expected):
    assert map_cobalt_error(code).code is expected

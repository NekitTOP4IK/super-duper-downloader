import pytest

from app.core.errors import EngineError, ErrorCode
from app.engines.base import DownloadOptions
from app.engines.router import EngineRouter
from app.models import Preset
from tests.fakes import FakeEngine, single, writes_file

URL = "https://example.com/v"


def make_router(*engines, sleeps=None):
    recorded = sleeps if sleeps is not None else []

    async def fake_sleep(seconds):
        recorded.append(seconds)

    return EngineRouter(engines, sleep=fake_sleep)


@pytest.fixture
def opts(tmp_path):
    return DownloadOptions(
        preset=Preset.BEST, dest_dir=tmp_path / "job", max_duration_sec=100, max_filesize_bytes=1000
    )


async def test_probe_uses_first_successful_engine():
    first, second = FakeEngine("a", probe=[single()]), FakeEngine("b", probe=[single()])
    info = await make_router(first, second).probe(URL)
    assert info.title == "Video"
    assert second.probe_calls == []


@pytest.mark.parametrize(
    "code", [ErrorCode.UNSUPPORTED, ErrorCode.BLOCKED, ErrorCode.EXTRACTION_FAILED]
)
async def test_falls_back_on_recoverable_codes(code):
    first = FakeEngine("a", probe=[EngineError(code)])
    second = FakeEngine("b", probe=[single()])
    await make_router(first, second).probe(URL)
    assert second.probe_calls == [URL]


@pytest.mark.parametrize(
    "code",
    [ErrorCode.PRIVATE, ErrorCode.GEO_BLOCKED, ErrorCode.TOO_LONG, ErrorCode.TOO_LARGE],
)
async def test_stops_on_final_codes(code):
    first = FakeEngine("a", probe=[EngineError(code)])
    second = FakeEngine("b", probe=[single()])
    with pytest.raises(EngineError) as info:
        await make_router(first, second).probe(URL)
    assert info.value.code is code
    assert second.probe_calls == []


async def test_network_errors_retry_with_backoff_then_fall_back():
    sleeps = []
    first = FakeEngine("a", probe=[EngineError(ErrorCode.NETWORK)])
    second = FakeEngine("b", probe=[single()])
    await make_router(first, second, sleeps=sleeps).probe(URL)
    assert len(first.probe_calls) == 3
    assert sleeps == [1.0, 2.0]
    assert second.probe_calls == [URL]


async def test_network_retry_can_succeed():
    first = FakeEngine("a", probe=[EngineError(ErrorCode.NETWORK), single()])
    await make_router(first).probe(URL)
    assert len(first.probe_calls) == 2


async def test_skips_engines_that_cannot_handle_url():
    skipped = FakeEngine("a", handles=False, probe=[single()])
    used = FakeEngine("b", probe=[single()])
    await make_router(skipped, used).probe(URL)
    assert skipped.probe_calls == []


async def test_no_capable_engine_is_unsupported():
    with pytest.raises(EngineError) as info:
        await make_router(FakeEngine(handles=False)).probe(URL)
    assert info.value.code is ErrorCode.UNSUPPORTED


async def test_unexpected_exception_is_internal_without_fallback():
    first = FakeEngine("a", probe=[RuntimeError("boom")])
    second = FakeEngine("b", probe=[single()])
    with pytest.raises(EngineError) as info:
        await make_router(first, second).probe(URL)
    assert info.value.code is ErrorCode.INTERNAL
    assert second.probe_calls == []


async def test_all_engines_failing_reports_the_first_specific_error():
    first = FakeEngine("a", probe=[EngineError(ErrorCode.UNSUPPORTED)])
    second = FakeEngine("b", probe=[EngineError(ErrorCode.BLOCKED, "login required")])
    third = FakeEngine("c", probe=[EngineError(ErrorCode.EXTRACTION_FAILED)])
    fourth = FakeEngine("d", probe=[EngineError(ErrorCode.UNSUPPORTED)])
    with pytest.raises(EngineError) as info:
        await make_router(first, second, third, fourth).probe(URL)
    assert info.value.code is ErrorCode.BLOCKED
    assert info.value.message == "login required"


async def test_all_engines_unsupported_stays_unsupported():
    first = FakeEngine("a", probe=[EngineError(ErrorCode.UNSUPPORTED)])
    second = FakeEngine("b", probe=[EngineError(ErrorCode.UNSUPPORTED)])
    with pytest.raises(EngineError) as info:
        await make_router(first, second).probe(URL)
    assert info.value.code is ErrorCode.UNSUPPORTED


async def test_download_resets_directory_between_engines(opts):
    def partial_then_blocked(o, on_progress):
        (o.dest_dir / "partial.bin").write_bytes(b"x")
        raise EngineError(ErrorCode.BLOCKED)

    first = FakeEngine("a", download=[partial_then_blocked])
    second = FakeEngine("b", download=[writes_file()])
    name, files = await make_router(first, second).download(URL, opts, lambda p: None)
    assert name == "b"
    assert [p.name for p in files] == ["video.mp4"]
    assert sorted(p.name for p in opts.dest_dir.iterdir()) == ["video.mp4"]

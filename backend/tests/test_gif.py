import subprocess

import pytest

from app import gif
from app.core.errors import EngineError, ErrorCode
from tests.fakes import make_video, needs_ffmpeg

HIGH, MEDIUM = gif.QUALITIES


def test_frame_size_brings_the_shorter_side_down_to_the_quality():
    assert gif.frame_size(1920, 1080, HIGH) == (853, 480)
    assert gif.frame_size(1080, 1920, MEDIUM) == (320, 569)


def test_frame_size_never_enlarges_a_small_video():
    assert gif.frame_size(320, 240, HIGH) == (320, 240)


def test_plan_takes_the_best_quality_that_fits_the_target():
    assert gif.plan(5, 1920, 1080) == [HIGH, MEDIUM]
    assert gif.plan(10, 1920, 1080) == [MEDIUM]


def test_plan_falls_back_to_the_lowest_quality_within_the_limit():
    # Estimated over the target at every quality, still under the hard limit at the lowest.
    assert gif.plan(30, 1920, 1080) == [MEDIUM]


def test_plan_gives_up_on_a_gif_over_the_limit_at_every_quality():
    assert gif.plan(120, 1920, 1080) == []


def test_plan_without_a_frame_size_assumes_a_widescreen_video():
    assert gif.plan(5, None, None) == gif.plan(5, 1920, 1080)


def test_plan_without_a_duration_tries_every_quality():
    assert gif.plan(None, 1920, 1080) == [HIGH, MEDIUM]


def test_estimate_is_offered_only_within_the_target():
    assert 0 < gif.estimate(5, 1920, 1080) <= gif.TARGET_BYTES
    assert gif.estimate(40, 1920, 1080) is None


def _sound(path):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1", str(path)],
        check=True,
    )
    return path


def _frame_size(path):
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return tuple(map(int, out.strip().split(",")))


@needs_ffmpeg
async def test_convert_turns_a_video_into_a_gif_in_its_place(tmp_path):
    source = make_video(tmp_path / "clip.mp4", duration=2)
    result = await gif.convert(source)
    assert result == tmp_path / "clip.gif"
    assert not source.exists()
    assert _frame_size(result) == (853, 480)


@needs_ffmpeg
async def test_convert_refuses_a_file_without_video(tmp_path):
    with pytest.raises(EngineError) as exc:
        await gif.convert(_sound(tmp_path / "sound.m4a"))
    assert exc.value.code is ErrorCode.NO_VIDEO


@needs_ffmpeg
async def test_convert_refuses_a_file_that_is_not_media(tmp_path):
    source = tmp_path / "notes.mp4"
    source.write_text("not a video")
    with pytest.raises(EngineError) as exc:
        await gif.convert(source)
    assert exc.value.code is ErrorCode.NO_VIDEO


@needs_ffmpeg
async def test_convert_steps_down_a_gif_over_the_target(tmp_path, monkeypatch):
    # Estimated well within the target, made far over it.
    monkeypatch.setattr(gif, "_BYTES_PER_PIXEL", 1e-6)
    monkeypatch.setattr(gif, "TARGET_BYTES", 1000)
    result = await gif.convert(make_video(tmp_path / "clip.mp4"))
    assert _frame_size(result) == (569, 320)


@needs_ffmpeg
async def test_convert_refuses_a_gif_heavier_than_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(gif, "TARGET_BYTES", 1000)
    monkeypatch.setattr(gif, "MAX_BYTES", 1000)
    source = make_video(tmp_path / "clip.mp4", size="640x360")
    with pytest.raises(EngineError) as exc:
        await gif.convert(source)
    assert exc.value.code is ErrorCode.TOO_LARGE
    assert not (tmp_path / "clip.gif").exists()


@needs_ffmpeg
async def test_convert_refuses_a_video_too_long_for_a_gif_without_encoding(tmp_path):
    source = make_video(tmp_path / "clip.mp4", rate=1, duration=200)
    with pytest.raises(EngineError) as exc:
        await gif.convert(source)
    assert exc.value.code is ErrorCode.TOO_LARGE
    assert source.exists()


@needs_ffmpeg
async def test_convert_keeps_a_gif_as_it_is(tmp_path):
    source = make_video(tmp_path / "anim.gif", size="64x64", rate=5)
    assert await gif.convert(source) == source

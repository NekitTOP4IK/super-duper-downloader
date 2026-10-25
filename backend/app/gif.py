"""GIFs made out of downloaded videos. A GIF weighs many times its video, so how long a video
may be and how small its frames get are worked out from an estimate of the GIF's size."""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import EngineError, ErrorCode

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Quality:
    side: int
    fps: int


QUALITIES = (Quality(480, 15), Quality(320, 10))
TARGET_BYTES = 15 * 1024 * 1024
MAX_BYTES = 30 * 1024 * 1024
# Bytes per pixel of every frame, measured at both qualities: from 0.14 for a cartoon and 0.25
# for an old music video to 0.45 for 4K nature footage and 0.9 for a busy street. A made GIF
# over the target is made again smaller, so the estimate leans to the heavy side only so far.
_BYTES_PER_PIXEL = 0.5
# Sites such as X give no frame size for their GIFs.
_ASSUMED_FRAME = (1920, 1080)
# Downloaded files come from anywhere, and an HLS playlist among them would send ffmpeg to
# fetch whatever it names.
_LOCAL_ONLY = ("-protocol_whitelist", "file")


def frame_size(width: int, height: int, quality: Quality) -> tuple[int, int]:
    scale = min(1.0, quality.side / min(width, height))
    return round(width * scale), round(height * scale)


def plan(duration: float | None, width: int | None, height: int | None) -> list[Quality]:
    """Qualities to try in turn, the first one expected to fit the target. Empty when even the
    lowest would pass the limit."""
    if not duration:
        return list(QUALITIES)
    sizes = _estimates(duration, width, height)
    for index, size in enumerate(sizes):
        if size <= TARGET_BYTES:
            return list(QUALITIES[index:])
    return [QUALITIES[-1]] if sizes[-1] <= MAX_BYTES else []


def estimate(duration: float, width: int | None, height: int | None) -> int | None:
    """Size of the GIF a video would make, where it fits the target."""
    return next(
        (size for size in _estimates(duration, width, height) if size <= TARGET_BYTES), None
    )


def _estimates(duration: float, width: int | None, height: int | None) -> list[int]:
    if not (width and height):
        width, height = _ASSUMED_FRAME
    sizes = []
    for quality in QUALITIES:
        frame_width, frame_height = frame_size(width, height, quality)
        sizes.append(int(frame_width * frame_height * quality.fps * duration * _BYTES_PER_PIXEL))
    return sizes


async def convert(source: Path) -> Path:
    """Replaces a video with its GIF."""
    if source.suffix.lower() == ".gif":
        return source
    width, height, duration = await _probe(source)
    qualities = plan(duration, width, height)
    if not qualities:
        raise _too_large()
    target = source.with_suffix(".gif")
    for index, quality in enumerate(qualities):
        await _encode(source, target, quality)
        size = target.stat().st_size
        if size <= TARGET_BYTES or (index == len(qualities) - 1 and size <= MAX_BYTES):
            source.unlink()
            return target
    target.unlink()
    raise _too_large()


async def _probe(source: Path) -> tuple[int, int, float | None]:
    out = await _run(
        "ffprobe",
        "-v",
        "error",
        *_LOCAL_ONLY,
        "-select_streams",
        "v",
        "-show_entries",
        "stream=width,height:stream_disposition=attached_pic:format=duration",
        "-of",
        "json",
        str(source),
    )
    if out is None:
        # ffprobe gives up on what is not media at all.
        raise _no_video()
    data = json.loads(out)
    # The cover of an audio file is a video stream of a single picture.
    streams = [
        stream
        for stream in data.get("streams") or []
        if stream.get("width") and not (stream.get("disposition") or {}).get("attached_pic")
    ]
    if not streams:
        raise _no_video()
    duration = (data.get("format") or {}).get("duration")
    return streams[0]["width"], streams[0]["height"], float(duration) if duration else None


async def _encode(source: Path, target: Path, quality: Quality) -> None:
    side = quality.side
    # The palette is built from this very video, and dithering in a fixed pattern keeps
    # neighbouring frames alike, which GIF compresses far better than random noise.
    filters = (
        f"fps={quality.fps},"
        f"scale='if(gt(iw,ih),-1,min({side},iw))':'if(gt(iw,ih),min({side},ih),-1)':flags=lanczos,"
        "split[a][b];[a]palettegen=stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    out = await _run(
        "ffmpeg", "-v", "error", "-y", *_LOCAL_ONLY, "-i", str(source), "-vf", filters, str(target)
    )
    if out is None:
        raise EngineError(ErrorCode.INTERNAL, "could not make a GIF")


async def _run(*args: str) -> str | None:
    """What a command prints, or None where it failed."""
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await process.communicate()
    if process.returncode != 0:
        log.info("%s failed: %s", args[0], err.decode(errors="replace")[-1000:])
        return None
    return out.decode()


def _too_large() -> EngineError:
    return EngineError(ErrorCode.TOO_LARGE, f"a GIF of this video would pass {MAX_BYTES >> 20} MB")


def _no_video() -> EngineError:
    return EngineError(ErrorCode.NO_VIDEO, "there is no video to make a GIF of")

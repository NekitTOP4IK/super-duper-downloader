import asyncio
import logging
import shutil
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from app.core.errors import FALLBACK_CODES, RETRY_CODES, EngineError, ErrorCode
from app.engines.base import DownloadOptions, Engine, ProgressCallback
from app.models import MediaInfo

log = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]

# When every engine fails, the user sees the most specific reason, and among equally specific
# ones the reason of the earliest engine. Generic engines answer UNSUPPORTED or
# EXTRACTION_FAILED for nearly anything, which would hide "login required" or "deleted".
_VAGUENESS = {
    ErrorCode.NETWORK: 1,
    ErrorCode.EXTRACTION_FAILED: 1,
    ErrorCode.UNSUPPORTED: 2,
}


class EngineRouter:
    def __init__(
        self,
        engines: Sequence[Engine],
        *,
        network_retries: int = 2,
        retry_delay: float = 1.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._engines = tuple(engines)
        self._network_retries = network_retries
        self._retry_delay = retry_delay
        self._sleep = sleep

    @property
    def engines(self) -> tuple[Engine, ...]:
        return self._engines

    async def probe(self, url: str) -> MediaInfo:
        _, info = await self._run(url, lambda engine: engine.probe(url))
        return info

    async def download(
        self, url: str, opts: DownloadOptions, on_progress: ProgressCallback
    ) -> tuple[str, list[Path]]:
        async def attempt(engine: Engine) -> list[Path]:
            _reset_dir(opts.dest_dir)
            return await engine.download(url, opts, on_progress)

        engine, files = await self._run(url, attempt)
        return engine.name, files

    async def _run[T](self, url: str, op: Callable[[Engine], Awaitable[T]]) -> tuple[Engine, T]:
        candidates = [engine for engine in self._engines if engine.can_handle(url)]
        if not candidates:
            raise EngineError(ErrorCode.UNSUPPORTED, "no engine can handle this URL")
        errors: list[EngineError] = []
        for engine in candidates:
            try:
                return engine, await self._attempt(engine, op)
            except EngineError as exc:
                log.info("engine %s failed for %s: %s %s", engine.name, url, exc.code, exc.message)
                errors.append(exc)
                if exc.code not in FALLBACK_CODES:
                    raise
        raise min(errors, key=lambda exc: _VAGUENESS.get(exc.code, 0))

    async def _attempt[T](self, engine: Engine, op: Callable[[Engine], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            try:
                return await op(engine)
            except EngineError as exc:
                if exc.code in RETRY_CODES and attempt < self._network_retries:
                    await self._sleep(self._retry_delay * 2**attempt)
                    attempt += 1
                    continue
                raise
            except Exception as exc:
                log.exception("engine %s crashed", engine.name)
                raise EngineError(ErrorCode.INTERNAL, f"{engine.name} failed unexpectedly") from exc


def _reset_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)

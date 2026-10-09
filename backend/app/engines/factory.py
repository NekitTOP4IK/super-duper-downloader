from app.core.config import Settings
from app.engines.cobalt import CobaltEngine
from app.engines.direct import DirectEngine
from app.engines.router import EngineRouter
from app.engines.ytdlp import YtDlpEngine


def build_router(settings: Settings) -> EngineRouter:
    return EngineRouter(
        [
            YtDlpEngine(proxy_url=settings.proxy_url, playlist_limit=settings.max_playlist_items),
            CobaltEngine(settings.cobalt_url),
            DirectEngine(proxy_url=settings.proxy_url),
        ]
    )

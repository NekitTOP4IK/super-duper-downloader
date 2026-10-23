from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

from app.api.routes import batches, files, limits, probe
from app.core.config import Settings
from app.queue import TaskQueue
from app.store.redis_store import Store

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    *,
    settings: Settings,
    store: Store | None = None,
    queue: TaskQueue | None = None,
    lifespan: Lifespan | None = None,
) -> FastAPI:
    app = FastAPI(title="super-duper-downloader", lifespan=lifespan)
    app.state.settings = settings
    if store is not None:
        app.state.store = store
    if queue is not None:
        app.state.queue = queue
    app.include_router(probe.router)
    app.include_router(batches.router)
    app.include_router(files.router)
    app.include_router(limits.router)
    return app

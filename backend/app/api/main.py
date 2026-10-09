from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from app.api.app import create_app
from app.core.config import get_settings
from app.queue import ArqTaskQueue
from app.store.redis_store import Store

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.store = Store(pool, settings.file_ttl_sec)
    app.state.queue = ArqTaskQueue(pool)
    yield
    await pool.aclose()


app = create_app(settings=settings, lifespan=lifespan)

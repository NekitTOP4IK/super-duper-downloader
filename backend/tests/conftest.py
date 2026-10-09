import fakeredis
import httpx
import pytest

from app.api.app import create_app
from app.core.config import Settings
from app.store.redis_store import Store
from tests.fakes import FakeQueue


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis()
    yield client
    await client.aclose()


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path / "data", min_free_disk_gb=0)


@pytest.fixture
def store(redis, settings):
    return Store(redis, settings.file_ttl_sec)


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
async def client(settings, store, queue):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(settings=settings, store=store, queue=queue)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

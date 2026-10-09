import fakeredis
import pytest

from app.core.config import Settings
from app.store.redis_store import Store


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

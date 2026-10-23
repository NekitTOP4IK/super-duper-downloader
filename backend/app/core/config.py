from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = Path("data")
    cobalt_url: str = "http://localhost:9000"
    proxy_url: str = ""
    egress_allow_cidrs: str = ""

    max_duration_sec: int = 10800
    max_filesize_mb: int = 2048
    max_batch_urls: int = 50
    max_playlist_items: int = 50
    max_queue: int = 500
    max_probe_queue: int = 100
    min_free_disk_gb: float = 5.0
    worker_concurrency: int = 3
    probe_concurrency: int = 10
    job_timeout_sec: int = 1800
    probe_timeout_sec: int = 30
    probe_cache_sec: int = 900
    file_ttl_hours: int = 6
    rate_probes_per_minute: int = 30
    rate_downloads_per_hour: int = 100

    @property
    def file_ttl_sec(self) -> int:
        return self.file_ttl_hours * 3600

    @property
    def max_filesize_bytes(self) -> int:
        return self.max_filesize_mb * 1024 * 1024

    @property
    def internal_hosts(self) -> set[str]:
        return _hosts(self.redis_url, self.cobalt_url)

    @property
    def egress_hosts(self) -> set[str]:
        return _hosts(self.proxy_url)


def _hosts(*urls: str) -> set[str]:
    return {host for url in urls if url and (host := urlsplit(url).hostname)}


@lru_cache
def get_settings() -> Settings:
    return Settings()

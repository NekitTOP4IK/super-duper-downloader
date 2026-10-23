from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.core.errors import FALLBACK_CODES, RETRY_CODES, EngineError, ErrorCode
from app.models import Job, JobStatus


def test_defaults_match_spec():
    s = Settings(_env_file=None)
    assert s.max_duration_sec == 10800
    assert s.max_filesize_bytes == 2048 * 1024 * 1024
    assert s.file_ttl_sec == 6 * 3600
    assert s.max_batch_urls == 50
    assert s.proxy_url == ""


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("MAX_BATCH_URLS", "7")
    monkeypatch.setenv("DATA_DIR", "/srv/files")
    s = Settings(_env_file=None)
    assert s.max_batch_urls == 7
    assert s.data_dir == Path("/srv/files")


def test_fallback_and_retry_codes():
    assert {
        ErrorCode.UNSUPPORTED,
        ErrorCode.BLOCKED,
        ErrorCode.EXTRACTION_FAILED,
        ErrorCode.NETWORK,
        ErrorCode.UNAVAILABLE,
    } == FALLBACK_CODES
    assert {ErrorCode.NETWORK} == RETRY_CODES


def test_engine_error_message_defaults_to_code():
    err = EngineError(ErrorCode.TOO_LONG)
    assert err.code is ErrorCode.TOO_LONG
    assert err.message == "TOO_LONG"
    assert EngineError(ErrorCode.PRIVATE, "private video").message == "private video"


def test_job_json_roundtrip():
    job = Job(id="j1", batch_id="b1", url="https://example.com", expires_at=datetime.now(UTC))
    restored = Job.model_validate_json(job.model_dump_json())
    assert restored == job
    assert restored.status is JobStatus.QUEUED

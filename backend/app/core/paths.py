from pathlib import Path

from app.models import Job


def job_dir(data_dir: Path, batch_id: str, job_id: str) -> Path:
    return data_dir / batch_id / job_id


def resolve_file(data_dir: Path, job: Job, name: str) -> Path | None:
    base = job_dir(data_dir, job.batch_id, job.id).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        return None
    return path

from pathlib import Path

from zipstream import ZIP_STORED, ZipStream

from app.core.paths import resolve_file
from app.models import Job, JobStatus


def unique_name(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    if not stem:
        stem, dot, ext = name, "", ""
    candidate, index = name, 2
    while candidate in used:
        candidate = f"{stem} ({index}){dot}{ext}"
        index += 1
    used.add(candidate)
    return candidate


def build_zip(data_dir: Path, jobs: list[Job]) -> ZipStream | None:
    archive = ZipStream(compress_type=ZIP_STORED, sized=True)
    used: set[str] = set()
    for job in jobs:
        if job.status is not JobStatus.DONE:
            continue
        for file in job.files:
            path = resolve_file(data_dir, job, file.name)
            if path is not None:
                archive.add_path(str(path), unique_name(file.name, used))
    return archive if used else None

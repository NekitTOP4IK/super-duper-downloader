from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from app.core.errors import ErrorCode


class Preset(StrEnum):
    BEST = "best"
    P1080 = "1080"
    P720 = "720"
    P480 = "480"
    AUDIO = "audio"


class MediaKind(StrEnum):
    SINGLE = "single"
    PLAYLIST = "playlist"


class PlaylistEntry(BaseModel):
    url: str
    title: str | None = None
    duration: float | None = None


class MediaInfo(BaseModel):
    kind: MediaKind
    url: str
    title: str | None = None
    thumbnail: str | None = None
    duration: float | None = None
    uploader: str | None = None
    presets: list[Preset] = []
    sizes: dict[Preset, int] = {}
    count: int | None = None
    entries: list[PlaylistEntry] = []


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    EXPANDED = "expanded"
    DONE = "done"
    FAILED = "failed"


class Progress(BaseModel):
    stage: Literal["downloading", "processing"] = "downloading"
    percent: float | None = None
    speed: float | None = None
    eta: float | None = None
    downloaded: int | None = None
    total: int | None = None


class FileInfo(BaseModel):
    name: str
    size: int


class JobError(BaseModel):
    code: ErrorCode
    message: str


class Job(BaseModel):
    id: str
    batch_id: str
    url: str
    status: JobStatus = JobStatus.QUEUED
    parent_id: str | None = None
    title: str | None = None
    engine: str | None = None
    progress: Progress | None = None
    files: list[FileInfo] = []
    error: JobError | None = None
    expires_at: datetime


class Batch(BaseModel):
    id: str
    owner_id: str | None = None
    preset: Preset
    created_at: datetime
    expires_at: datetime

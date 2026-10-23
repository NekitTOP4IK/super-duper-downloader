from pydantic import BaseModel, Field

from app.models import Batch, Job, Preset


class ProbeRequest(BaseModel):
    url: str = Field(max_length=4096)


class BatchRequest(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=1000)
    text: str = Field(default="", max_length=200_000)
    preset: Preset = Preset.BEST


class BatchCreated(BaseModel):
    batch_id: str
    jobs: int
    truncated: bool


class BatchState(BaseModel):
    batch: Batch
    jobs: list[Job]


class Limits(BaseModel):
    max_batch_urls: int
    max_playlist_items: int

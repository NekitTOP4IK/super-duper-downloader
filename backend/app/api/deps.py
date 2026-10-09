from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.queue import TaskQueue
from app.store.redis_store import Store

ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


@dataclass(frozen=True)
class Requester:
    id: str | None = None


async def get_requester() -> Requester:
    return Requester()


def _store(request: Request) -> Store:
    return request.app.state.store


def _queue(request: Request) -> TaskQueue:
    return request.app.state.queue


def _settings(request: Request) -> Settings:
    return request.app.state.settings


StoreDep = Annotated[Store, Depends(_store)]
QueueDep = Annotated[TaskQueue, Depends(_queue)]
SettingsDep = Annotated[Settings, Depends(_settings)]
RequesterDep = Annotated[Requester, Depends(get_requester)]

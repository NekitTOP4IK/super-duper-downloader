from fastapi import APIRouter

from app.api.deps import SettingsDep
from app.api.schemas import Limits

router = APIRouter(prefix="/api")


@router.get("/limits")
async def limits(settings: SettingsDep) -> Limits:
    return Limits(
        max_batch_urls=settings.max_batch_urls, max_playlist_items=settings.max_playlist_items
    )

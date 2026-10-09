from fastapi import APIRouter

from app.api.deps import QueueDep, RequesterDep, SettingsDep
from app.api.errors import ApiErrorCode, api_error
from app.api.schemas import ProbeRequest
from app.core.urls import extract_urls
from app.models import MediaInfo

router = APIRouter(prefix="/api")


@router.post("/probe")
async def probe(
    body: ProbeRequest, settings: SettingsDep, queue: QueueDep, _requester: RequesterDep
) -> MediaInfo:
    urls = extract_urls(body.url)
    if not urls:
        raise api_error(422, ApiErrorCode.NO_URLS, "no http(s) URL found")
    if await queue.probe_queue_length() >= settings.max_probe_queue:
        raise api_error(503, ApiErrorCode.BUSY, "server is busy, try again later")
    try:
        result = await queue.probe(urls[0], settings.probe_timeout_sec)
    except TimeoutError as exc:
        raise api_error(504, ApiErrorCode.PROBE_TIMEOUT, "probe took too long") from exc
    if not result["ok"]:
        error = result["error"]
        raise api_error(422, error["code"], error["message"])
    return MediaInfo.model_validate(result["info"])

from enum import StrEnum

from fastapi import HTTPException


class ApiErrorCode(StrEnum):
    BUSY = "BUSY"
    NO_URLS = "NO_URLS"
    NOT_FOUND = "NOT_FOUND"
    NO_FILES = "NO_FILES"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"


def api_error(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": str(code), "message": message},
        headers=headers,
    )

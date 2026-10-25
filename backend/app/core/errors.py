from enum import StrEnum


class ErrorCode(StrEnum):
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    NETWORK = "NETWORK"
    PRIVATE = "PRIVATE"
    GEO_BLOCKED = "GEO_BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    NO_AUDIO = "NO_AUDIO"
    NO_VIDEO = "NO_VIDEO"
    TOO_LONG = "TOO_LONG"
    TOO_LARGE = "TOO_LARGE"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL = "INTERNAL"


# "Login required" or "deleted" from one engine often only means its way into the site failed,
# so the next engine still gets a try.
FALLBACK_CODES = frozenset(
    {
        ErrorCode.UNSUPPORTED,
        ErrorCode.BLOCKED,
        ErrorCode.EXTRACTION_FAILED,
        ErrorCode.NETWORK,
        ErrorCode.UNAVAILABLE,
        ErrorCode.PRIVATE,
        ErrorCode.GEO_BLOCKED,
        ErrorCode.NO_AUDIO,
    }
)
RETRY_CODES = frozenset({ErrorCode.NETWORK})


class EngineError(Exception):
    def __init__(self, code: ErrorCode, message: str = "") -> None:
        self.code = code
        self.message = message or code.value
        super().__init__(self.message)

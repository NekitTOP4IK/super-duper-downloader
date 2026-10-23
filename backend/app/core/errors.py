from enum import StrEnum


class ErrorCode(StrEnum):
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    NETWORK = "NETWORK"
    PRIVATE = "PRIVATE"
    GEO_BLOCKED = "GEO_BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    TOO_LONG = "TOO_LONG"
    TOO_LARGE = "TOO_LARGE"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL = "INTERNAL"


FALLBACK_CODES = frozenset(
    {
        ErrorCode.UNSUPPORTED,
        ErrorCode.BLOCKED,
        ErrorCode.EXTRACTION_FAILED,
        ErrorCode.NETWORK,
        ErrorCode.UNAVAILABLE,
    }
)
RETRY_CODES = frozenset({ErrorCode.NETWORK})


class EngineError(Exception):
    def __init__(self, code: ErrorCode, message: str = "") -> None:
        self.code = code
        self.message = message or code.value
        super().__init__(self.message)

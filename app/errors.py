"""Structured API errors (SRS 24)."""

from __future__ import annotations

from typing import Any


class ErrorCode:
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_REQUEST = "INVALID_REQUEST"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    UNSUPPORTED_VOICE = "UNSUPPORTED_VOICE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    TTS_GENERATION_FAILED = "TTS_GENERATION_FAILED"
    SERVER_BUSY = "SERVER_BUSY"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIError(Exception):
    """Raised anywhere in the stack; rendered as a structured JSON body.

    Never carries stack traces or secrets into the response.
    """

    def __init__(self, code: str, message: str, status_code: int = 400, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra

    def to_payload(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, **self.extra}


def unauthorized(message: str = "Invalid API key.") -> APIError:
    return APIError(ErrorCode.UNAUTHORIZED, message, status_code=401)

"""Request/response schemas (SRS 31)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"error": "TEXT_TOO_LONG", "message": "Text exceeds the maximum allowed length."}
        }
    )

    error: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    model_loaded: bool
    provider: str | None = None
    model_id: str | None = None
    model_revision: str | None = None
    detail: str | None = None


class Voice(BaseModel):
    id: str
    name: str
    language: str
    gender: str | None = None
    description: str | None = None


class VoiceListResponse(BaseModel):
    voices: list[Voice]
    default_voice: str


class SpeechRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "The most important thing is to focus on one task at a time.",
                "language": "en",
                "voice": "default",
                "format": "mp3",
            }
        }
    )

    text: str = Field(..., description="Text to speak.", examples=["Hello world."])
    language: str | None = Field(default=None, description="Language code, e.g. 'en'.")
    voice: str | None = Field(default=None, description="Voice id from GET /v1/voices.")
    format: str | None = Field(default=None, description="Output format: mp3 or wav.")
    speed: float | None = Field(default=None, ge=0.5, le=2.0, description="Playback speed multiplier.")


class InfoResponse(BaseModel):
    app: str
    version: str
    environment: str
    provider: str
    model: dict[str, Any]
    defaults: dict[str, Any]
    limits: dict[str, Any]
    formats: list[str]
    languages: list[str]
    voice_count: int
    ready: bool

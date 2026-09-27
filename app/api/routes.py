"""HTTP routes (SRS 32)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import ClientContext, settings_dependency, verify_api_key
from app.api.schemas import (
    HealthResponse,
    InfoResponse,
    ReadyResponse,
    SpeechRequest,
    Voice,
    VoiceListResponse,
)
from app.config import Settings
from app.errors import APIError, ErrorCode
from app.logging_config import get_logger
from app.providers.kokoro import LANG_CODE_BY_LANGUAGE
from app.state import get_runtime

logger = get_logger(__name__)

router = APIRouter()

DEFAULT_VOICE_ALIAS = "default"


def _resolve_voice(voice: str | None, settings: Settings, provider) -> str:
    candidate = (voice or DEFAULT_VOICE_ALIAS).strip()
    if candidate == DEFAULT_VOICE_ALIAS:
        return settings.default_voice
    if not provider.supports_voice(candidate):
        raise APIError(
            ErrorCode.UNSUPPORTED_VOICE,
            f"Voice '{candidate}' is not available. See GET /v1/voices.",
            status_code=400,
        )
    return candidate


@router.get("/health", response_model=HealthResponse, tags=["system"], summary="Liveness probe")
def health(settings: Settings = Depends(settings_dependency)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadyResponse, tags=["system"], summary="Model readiness probe")
def ready(settings: Settings = Depends(settings_dependency)):
    from fastapi.responses import JSONResponse

    runtime = get_runtime()
    payload = ReadyResponse(
        status="ready" if runtime.is_ready() else "not_ready",
        model_loaded=runtime.is_ready(),
        provider=runtime.provider.name,
        model_id=settings.model_id,
        model_revision=settings.model_revision,
        detail=runtime.status_detail(),
    )
    if not runtime.is_ready():
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload


@router.get(
    "/v1/info",
    response_model=InfoResponse,
    tags=["tts"],
    summary="Service capabilities and limits",
    dependencies=[Depends(verify_api_key)],
)
def info(settings: Settings = Depends(settings_dependency)) -> InfoResponse:
    runtime = get_runtime()
    provider = runtime.provider
    return InfoResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        provider=provider.name,
        model=provider.model_info(),
        defaults={
            "language": settings.default_language,
            "voice": settings.default_voice,
            "format": settings.default_format,
            "speed": settings.default_speed,
        },
        limits={
            "max_text_length": settings.max_text_length,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "max_concurrency": settings.max_concurrency,
            "queue_timeout_seconds": settings.queue_timeout_seconds,
        },
        formats=settings.formats,
        languages=sorted(LANG_CODE_BY_LANGUAGE),
        voice_count=len(provider.list_voices()),
        ready=runtime.is_ready(),
    )


@router.get(
    "/v1/voices",
    response_model=VoiceListResponse,
    tags=["tts"],
    summary="List available voices",
    dependencies=[Depends(verify_api_key)],
)
def voices(settings: Settings = Depends(settings_dependency)) -> VoiceListResponse:
    provider = get_runtime().provider
    return VoiceListResponse(
        voices=[Voice(**v.to_dict()) for v in provider.list_voices()],
        default_voice=settings.default_voice,
    )


@router.post(
    "/v1/speech",
    tags=["tts"],
    summary="Generate speech",
    response_class=Response,
    responses={
        200: {
            "content": {"audio/mpeg": {}, "audio/wav": {}},
            "description": "The generated audio.",
        },
        400: {"description": "Validation error."},
        401: {"description": "Missing or invalid API key."},
        413: {"description": "Text too long."},
        429: {"description": "Rate limit exceeded."},
        503: {"description": "Model not ready or server busy."},
    },
)
async def speech(
    payload: SpeechRequest,
    request: Request,
    response: Response,
    client: ClientContext = Depends(verify_api_key),
    settings: Settings = Depends(settings_dependency),
) -> Response:
    runtime = get_runtime()
    provider = runtime.provider

    text = (payload.text or "").strip()
    if not text:
        raise APIError(ErrorCode.INVALID_REQUEST, "Text must not be empty.", status_code=400)
    if len(text) > settings.max_text_length:
        raise APIError(
            ErrorCode.TEXT_TOO_LONG,
            f"Text exceeds the maximum allowed length of {settings.max_text_length} characters.",
            status_code=413,
        )

    language = (payload.language or settings.default_language).lower()
    if not provider.supports_language(language):
        raise APIError(
            ErrorCode.UNSUPPORTED_LANGUAGE,
            f"Language '{language}' is not supported.",
            status_code=400,
            supported_languages=sorted(LANG_CODE_BY_LANGUAGE),
        )

    output_format = (payload.format or settings.default_format).lower()
    if output_format not in settings.formats:
        raise APIError(
            ErrorCode.UNSUPPORTED_FORMAT,
            f"Format '{output_format}' is not supported.",
            status_code=400,
            supported_formats=settings.formats,
        )

    voice = _resolve_voice(payload.voice, settings, provider)
    speed = payload.speed or settings.default_speed

    audio_bytes, media_type, result = await runtime.service.generate(
        text,
        voice=voice,
        language=language,
        output_format=output_format,
        speed=speed,
    )

    request.state.audio_seconds = result.duration_seconds
    request.state.generation_seconds = result.generation_seconds
    request.state.characters = len(text)

    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "X-Voice": voice,
            "X-Language": language,
            "X-Audio-Duration-Seconds": f"{result.duration_seconds:.3f}",
            "X-Generation-Seconds": f"{result.generation_seconds:.3f}",
            "X-Server-Seconds": f"{result.server_seconds:.3f}",
            "X-Real-Time-Factor": f"{result.real_time_factor:.3f}",
            "X-Provider": result.provider,
        },
    )

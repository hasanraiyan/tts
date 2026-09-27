"""TTS orchestration: concurrency control + provider invocation + encoding.

Kokoro inference is CPU-bound and not safe to run concurrently on the same
model instance, so requests are queued behind a semaphore (SRS 29) and the
blocking work is pushed to a worker thread so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace

from app.config import Settings
from app.errors import APIError, ErrorCode
from app.logging_config import get_logger
from app.providers.base import AudioResult, TTSProvider
from app.services.audio import encode

logger = get_logger(__name__)


class TTSService:
    def __init__(self, provider: TTSProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings
        self._semaphore = asyncio.Semaphore(max(1, settings.max_concurrency))

    @property
    def provider(self) -> TTSProvider:
        return self._provider

    def is_ready(self) -> bool:
        return self._provider.is_loaded()

    async def generate(
        self,
        text: str,
        *,
        voice: str,
        language: str,
        output_format: str,
        speed: float,
    ) -> tuple[bytes, str, AudioResult]:
        if not self._provider.is_loaded():
            raise APIError(
                ErrorCode.MODEL_NOT_READY,
                "TTS model is still loading. Retry shortly.",
                status_code=503,
            )

        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self._settings.queue_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise APIError(
                ErrorCode.SERVER_BUSY,
                "Server is busy, retry later.",
                status_code=503,
            ) from exc

        try:
            started = time.perf_counter()
            result = await asyncio.to_thread(
                self._provider.synthesize,
                text,
                voice=voice,
                language=language,
                speed=speed,
            )
            audio_bytes, media_type = await asyncio.to_thread(
                encode, result.samples, result.sample_rate, output_format
            )
            # AudioResult is frozen: time the encode step into a new instance.
            result = replace(result, server_seconds=time.perf_counter() - started)
            return audio_bytes, media_type, result
        except APIError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak internals to clients
            logger.exception("tts generation failed voice=%s lang=%s", voice, language)
            raise APIError(
                ErrorCode.TTS_GENERATION_FAILED,
                "Speech generation failed.",
                status_code=500,
            ) from exc
        finally:
            self._semaphore.release()

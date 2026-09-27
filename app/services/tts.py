"""TTS orchestration: concurrency control + provider invocation + encoding.

Kokoro inference is CPU-bound and must not run twice at once on the same model,
so every caller (HTTP request or background job worker) takes the same slot.
The slot is a *threading* semaphore on purpose: the job worker is a thread and
the request path is async, and a threading lock is the only primitive both can
share. The async path acquires it inside a worker thread, so the event loop is
never blocked.
"""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import Callable, Iterator, TypeVar

from app.config import Settings
from app.errors import APIError, ErrorCode
from app.logging_config import get_logger
from app.providers.base import AudioResult, TTSProvider
from app.services.audio import encode

logger = get_logger(__name__)

T = TypeVar("T")


class TTSService:
    def __init__(self, provider: TTSProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings
        self._slot = threading.Semaphore(max(1, settings.max_concurrency))
        self._queue_depth = 0
        self._queue_lock = threading.Lock()

    @property
    def provider(self) -> TTSProvider:
        return self._provider

    def is_ready(self) -> bool:
        return self._provider.is_loaded()

    @property
    def sample_rate(self) -> int:
        return self._settings.sample_rate

    @property
    def queue_depth(self) -> int:
        with self._queue_lock:
            return self._queue_depth

    def _enter(self) -> None:
        with self._queue_lock:
            self._queue_depth += 1

    def _leave(self) -> None:
        with self._queue_lock:
            self._queue_depth = max(0, self._queue_depth - 1)

    @contextmanager
    def slot(self, timeout: float | None = None) -> Iterator[None]:
        """Exclusive access to the model. Raises SERVER_BUSY on timeout."""
        wait = self._settings.queue_timeout_seconds if timeout is None else timeout
        if not self._slot.acquire(timeout=wait):
            raise APIError(
                ErrorCode.SERVER_BUSY,
                "Server is busy, retry later.",
                status_code=503,
            )
        self._enter()
        try:
            yield
        finally:
            self._leave()
            self._slot.release()

    def run_exclusive(self, work: Callable[[], T], timeout: float | None = None) -> T:
        """Run `work` while holding the model slot. Thread-safe."""
        with self.slot(timeout):
            return work()

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

        def work() -> tuple[bytes, str, AudioResult]:
            started = time.perf_counter()
            result = self._provider.synthesize(
                text, voice=voice, language=language, speed=speed
            )
            audio_bytes, media_type = encode(result.samples, result.sample_rate, output_format)
            # AudioResult is frozen: time the encode step into a new instance.
            return audio_bytes, media_type, replace(
                result, server_seconds=time.perf_counter() - started
            )

        try:
            return await asyncio.to_thread(self.run_exclusive, work)
        except APIError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak internals to clients
            logger.exception("tts generation failed voice=%s lang=%s", voice, language)
            raise APIError(
                ErrorCode.TTS_GENERATION_FAILED,
                "Speech generation failed.",
                status_code=500,
            ) from exc

"""Process-wide runtime state: provider, service, and readiness.

Kept in its own module so routes and the app factory share one instance and
tests can reset it.
"""

from __future__ import annotations

from app.config import Settings
from app.providers.base import TTSProvider
from app.providers.kokoro import KokoroProvider
from app.services.tts import TTSService


class Runtime:
    def __init__(self, settings: Settings, provider: TTSProvider | None = None) -> None:
        self.settings = settings
        self.provider: TTSProvider = provider or KokoroProvider(settings)
        self.service = TTSService(self.provider, settings)
        self.ready = False
        self.detail: str | None = None

    def is_ready(self) -> bool:
        return self.ready and self.provider.is_loaded()

    def status_detail(self) -> str | None:
        if self.is_ready():
            return None
        return self.detail or "model is not loaded"

    def load(self) -> None:
        try:
            self.provider.load()
            self.ready = True
            self.detail = None
        except Exception as exc:  # noqa: BLE001 - surfaced through /ready
            self.ready = False
            self.detail = f"{type(exc).__name__}: {exc}"
            raise


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime(get_settings_singleton())
    return _runtime


def set_runtime(runtime: Runtime | None) -> None:
    global _runtime
    _runtime = runtime


def get_settings_singleton() -> Settings:
    from app.config import get_settings

    return get_settings()

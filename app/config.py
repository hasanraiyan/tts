"""Configuration for the TTS service.

Secrets are only ever read from the environment. `.env` is loaded for local
development only; on Render everything comes from real environment variables.
"""

from __future__ import annotations

import os
from typing import Mapping

from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so third-party libraries (huggingface_hub, torch)
# also see variables such as HF_HOME / HF_TOKEN. Never overrides real env vars.
load_dotenv(override=False)

API_KEY_PREFIX = "API_KEY_"


def collect_api_keys(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Map client_id -> api key from ``API_KEY_<CLIENT_ID>`` variables.

    Deliberately generic: onboarding a new consuming application is a matter of
    setting one environment variable, with no code change. ``API_KEY`` alone is
    accepted as the ``default`` client for quick local testing.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    keys: dict[str, str] = {}
    for name, value in source.items():
        if not name.startswith(API_KEY_PREFIX):
            continue
        client_id = name[len(API_KEY_PREFIX) :].strip().lower().replace("_", "-")
        if client_id and value.strip():
            keys[client_id] = value.strip()
    single = source.get("API_KEY", "").strip()
    if single:
        keys.setdefault("default", single)
    return keys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Application
    app_name: str = "ai-tts-service"
    app_version: str = "1.0.0"
    app_env: str = "production"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Hugging Face
    hf_token: SecretStr | None = None
    hf_home: str | None = None

    # Model
    model_id: str = "hexgrad/Kokoro-82M"
    model_revision: str = "f3ff3571791e39611d31c381e3a41a3af07b4987"
    model_weights_file: str = "kokoro-v1_0.pth"

    # Which TTS runtime to use: "onnx" (fits 512MB) or "torch" (best quality)
    tts_provider: str = "onnx"
    onnx_model_dir: str = "/app/models/kokoro-int8-multi-lang-v1_0"
    onnx_num_threads: int = 1

    # TTS defaults / capabilities
    default_language: str = "en"
    default_voice: str = "af_heart"
    default_format: str = "mp3"
    supported_formats: str = "mp3,wav"
    max_text_length: int = 5000
    sample_rate: int = 24000
    default_speed: float = 1.0

    # Runtime / protection
    rate_limit_per_minute: int = 30
    max_concurrency: int = 1
    queue_timeout_seconds: float = 120.0
    torch_num_threads: int = 4
    preload_model: bool = True

    # Asynchronous job queue settings live in app/services/jobs.py as constants.
    # They are deliberately not environment variables: the defaults are correct
    # for every deployment target, so there is nothing to configure.

    @property
    def formats(self) -> list[str]:
        return [f.strip().lower() for f in self.supported_formats.split(",") if f.strip()]

    @property
    def api_keys(self) -> dict[str, str]:
        return collect_api_keys()

    def hf_token_value(self) -> str | None:
        return self.hf_token.get_secret_value() if self.hf_token else None


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

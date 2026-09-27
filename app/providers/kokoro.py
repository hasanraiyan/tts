"""Kokoro provider (SRS 5/16/17-21).

Everything Kokoro-specific lives here: Hugging Face download with a pinned
revision, voice handling, and CPU inference. The API layer never imports
`kokoro` directly.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

from app.config import Settings
from app.logging_config import get_logger
from app.providers.base import AudioResult, TTSProvider, Voice
from app.providers.voices import (
    VOICE_DESCRIPTIONS,
    voice_display_name,
    voice_gender,
)

logger = get_logger(__name__)

# lang_code understood by Kokoro's English pipelines.
LANG_CODE_BY_LANGUAGE = {"en": "a"}


class KokoroProvider(TTSProvider):
    name = "kokoro"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._pipeline = None
        self._voices: dict[str, Voice] = {}
        self._load_lock = threading.Lock()
        self._snapshot_dir: str | None = None
        self._load_seconds: float | None = None

    # ------------------------------------------------------------------ load

    def load(self) -> None:
        with self._load_lock:
            if self._model is not None:
                return
            started = time.perf_counter()
            import torch
            from huggingface_hub import snapshot_download
            from kokoro import KModel, KPipeline

            settings = self._settings
            torch.set_num_threads(max(1, settings.torch_num_threads))
            torch.set_grad_enabled(False)

            token = settings.hf_token_value()
            if token:
                # huggingface_hub also reads HF_TOKEN from the environment, so
                # any library-internal Hub call is authenticated too.
                os.environ["HF_TOKEN"] = token
            logger.info(
                "loading model id=%s revision=%s hf_auth=%s",
                settings.model_id,
                settings.model_revision,
                "yes" if token else "no",
            )
            # Pinned revision + local cache => identical weights everywhere and
            # no network calls once cached (SRS 19/20/21).
            local_dir = snapshot_download(
                repo_id=settings.model_id,
                revision=settings.model_revision,
                token=token,
                allow_patterns=[
                    "config.json",
                    settings.model_weights_file,
                    "voices/*.pt",
                ],
            )
            self._snapshot_dir = local_dir

            model = KModel(
                repo_id=settings.model_id,
                config=os.path.join(local_dir, "config.json"),
                model=os.path.join(local_dir, settings.model_weights_file),
            )
            self._model = model.to("cpu").eval()
            self._pipeline = KPipeline(
                lang_code=LANG_CODE_BY_LANGUAGE[settings.default_language],
                repo_id=settings.model_id,
                model=self._model,
                device="cpu",
            )
            self._load_voices(Path(local_dir) / "voices")
            self._load_seconds = time.perf_counter() - started
            logger.info(
                "model ready in %.1fs voices=%d sample_rate=%d",
                self._load_seconds,
                len(self._voices),
                settings.sample_rate,
            )

    def _load_voices(self, voices_dir: Path) -> None:
        import torch

        pack_dir = Path(voices_dir)
        for path in sorted(pack_dir.glob("*.pt")):
            voice_id = path.stem
            # Pre-seed the pipeline so it never hits the Hub at request time.
            self._pipeline.voices[voice_id] = torch.load(path, weights_only=True)
            self._voices[voice_id] = Voice(
                id=voice_id,
                name=voice_display_name(voice_id),
                language="en",
                gender=voice_gender(voice_id),
                description=VOICE_DESCRIPTIONS.get(voice_id),
            )

    def is_loaded(self) -> bool:
        return self._model is not None and self._pipeline is not None

    # ------------------------------------------------------------- discovery

    def list_voices(self) -> list[Voice]:
        return sorted(self._voices.values(), key=lambda v: v.id)

    def supports_language(self, language: str) -> bool:
        return language.lower() in LANG_CODE_BY_LANGUAGE

    def list_languages(self) -> list[str]:
        return sorted(LANG_CODE_BY_LANGUAGE)

    def supports_voice(self, voice_id: str) -> bool:
        return voice_id in self._voices

    def model_info(self) -> dict[str, str]:
        return {
            "provider": self.name,
            "model_id": self._settings.model_id,
            "model_revision": self._settings.model_revision,
            "load_seconds": f"{self._load_seconds:.2f}" if self._load_seconds else "unknown",
            "snapshot_dir": self._snapshot_dir or "unloaded",
        }

    # ------------------------------------------------------------ synthesize

    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        language: str,
        speed: float = 1.0,
    ) -> AudioResult:
        import torch

        if not self.is_loaded():
            raise RuntimeError("model is not loaded")

        started = time.perf_counter()
        chunks: list[np.ndarray] = []
        with torch.inference_mode():
            for result in self._pipeline(text, voice=voice, speed=speed):
                audio = result.audio
                if audio is None:
                    continue
                chunks.append(audio.detach().to("cpu").float().numpy().reshape(-1))
        generation_seconds = time.perf_counter() - started

        if not chunks:
            raise RuntimeError("provider produced no audio samples")

        samples = np.concatenate(chunks).astype(np.float32, copy=False)
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak > 1.0:
            samples = samples / peak

        return AudioResult(
            samples=samples,
            sample_rate=self._settings.sample_rate,
            voice=voice,
            language=language,
            provider=self.name,
            generation_seconds=generation_seconds,
            model_id=self._settings.model_id,
            model_revision=self._settings.model_revision,
        )

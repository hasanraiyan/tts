"""Kokoro v1.0 on ONNX Runtime (sherpa-onnx).

Why this provider exists: the PyTorch provider needs ~1.3GB of RAM, which does
not fit Render's 512MB plans. This one peaks at ~370MB for the same model, so
the same API runs on the smallest instance Render offers.

The model is the same Apache-2.0 Kokoro v1.0, int8-quantised, published by
sherpa-onnx. Voices are addressed by integer speaker id rather than by file
name, so the name -> id table lives in `app.providers.voices`.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from app.config import Settings
from app.logging_config import get_logger
from app.providers.base import AudioResult, TTSProvider, Voice
from app.providers.voices import (
    KOKORO_VOICE_IDS,
    VOICE_DESCRIPTIONS,
    voice_display_name,
    voice_gender,
)

logger = get_logger(__name__)

# English only for now, matching the PyTorch provider.
LANGUAGES = {"en"}

# Files that must exist in the model directory for this provider to work.
REQUIRED_FILES = (
    "model.int8.onnx",
    "voices.bin",
    "tokens.txt",
    "lexicon-us-en.txt",
    "espeak-ng-data",
)


class KokoroOnnxProvider(TTSProvider):
    name = "kokoro-onnx"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tts = None
        self._load_lock = threading.Lock()
        self._load_seconds: float | None = None

    # ------------------------------------------------------------------ load

    def load(self) -> None:
        with self._load_lock:
            if self._tts is not None:
                return
            started = time.perf_counter()
            import sherpa_onnx

            model_dir = Path(self._settings.onnx_model_dir)
            missing = [f for f in REQUIRED_FILES if not (model_dir / f).exists()]
            if missing:
                raise FileNotFoundError(
                    f"ONNX model directory {model_dir} is missing {missing}. "
                    "Set ONNX_MODEL_DIR or build the image with the model baked in."
                )

            threads = max(1, self._settings.onnx_num_threads)
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                        model=str(model_dir / "model.int8.onnx"),
                        voices=str(model_dir / "voices.bin"),
                        tokens=str(model_dir / "tokens.txt"),
                        lexicon=str(model_dir / "lexicon-us-en.txt"),
                        data_dir=str(model_dir / "espeak-ng-data"),
                        dict_dir=str(model_dir / "dict"),
                        lang="en-us",
                    ),
                    num_threads=threads,
                    provider="cpu",
                ),
                rule_fsts="",
                max_num_sentences=1,
            )
            self._tts = sherpa_onnx.OfflineTts(config)
            self._load_seconds = time.perf_counter() - started
            logger.info(
                "onnx model ready in %.1fs voices=%d sample_rate=%d threads=%d",
                self._load_seconds,
                self._tts.num_speakers,
                self._tts.sample_rate,
                threads,
            )

    def is_loaded(self) -> bool:
        return self._tts is not None

    # ------------------------------------------------------------- discovery

    def list_voices(self) -> list[Voice]:
        return [
            Voice(
                id=voice_id,
                name=voice_display_name(voice_id),
                language="en",
                gender=voice_gender(voice_id),
                description=VOICE_DESCRIPTIONS.get(voice_id),
            )
            for voice_id in sorted(KOKORO_VOICE_IDS)
        ]

    def supports_language(self, language: str) -> bool:
        return language.lower() in LANGUAGES

    def list_languages(self) -> list[str]:
        return sorted(LANGUAGES)

    def supports_voice(self, voice_id: str) -> bool:
        return voice_id in KOKORO_VOICE_IDS

    def model_info(self) -> dict[str, str]:
        return {
            "provider": self.name,
            "runtime": "sherpa-onnx",
            "model": "kokoro-int8-multi-lang-v1_0",
            "model_license": "Apache-2.0",
            "model_dir": self._settings.onnx_model_dir,
            "load_seconds": f"{self._load_seconds:.2f}" if self._load_seconds else "unknown",
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
        if self._tts is None:
            raise RuntimeError("model is not loaded")
        if voice not in KOKORO_VOICE_IDS:
            raise ValueError(f"unknown voice: {voice}")

        started = time.perf_counter()
        audio = self._tts.generate(text, sid=KOKORO_VOICE_IDS[voice], speed=speed)
        generation_seconds = time.perf_counter() - started

        samples = np.asarray(audio.samples, dtype=np.float32)
        if samples.size == 0:
            raise RuntimeError("provider produced no audio samples")
        peak = float(np.max(np.abs(samples)))
        if peak > 1.0:
            samples = samples / peak

        return AudioResult(
            samples=samples,
            sample_rate=audio.sample_rate,
            voice=voice,
            language=language,
            provider=self.name,
            generation_seconds=generation_seconds,
        )

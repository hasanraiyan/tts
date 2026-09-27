"""TTS provider abstraction (SRS 16).

The HTTP layer depends only on this interface, so the underlying model can be
replaced without any client-visible API change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str
    gender: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "gender": self.gender,
            "description": self.description,
        }


@dataclass(frozen=True)
class AudioResult:
    """Mono float32 PCM in [-1, 1] plus its sample rate."""

    samples: np.ndarray
    sample_rate: int
    voice: str
    language: str
    provider: str
    generation_seconds: float = 0.0
    server_seconds: float = 0.0
    model_id: str = ""
    model_revision: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return float(len(self.samples)) / float(self.sample_rate)

    @property
    def real_time_factor(self) -> float:
        duration = self.duration_seconds
        if duration <= 0:
            return 0.0
        return self.generation_seconds / duration


class TTSProvider(ABC):
    """Contract every provider must satisfy."""

    name: str = "base"

    @abstractmethod
    def load(self) -> None:
        """Download (if needed) and load the model. Called once at startup."""

    @abstractmethod
    def is_loaded(self) -> bool:
        ...

    @abstractmethod
    def list_voices(self) -> list[Voice]:
        ...

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        ...

    @abstractmethod
    def supports_voice(self, voice_id: str) -> bool:
        ...

    def list_languages(self) -> list[str]:
        """Language codes this provider can speak, for discovery endpoints."""
        return []

    @abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        language: str,
        speed: float = 1.0,
    ) -> AudioResult:
        ...

    def model_info(self) -> dict[str, str]:
        return {}

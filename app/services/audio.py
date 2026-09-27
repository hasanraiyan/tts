"""Audio encoding helpers.

Writes WAV and MP3 straight from numpy via libsndfile (bundled with
soundfile >= 0.12), so no ffmpeg binary is required in the runtime image.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

MEDIA_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
}

SF_FORMATS = {
    "wav": "WAV",
    "mp3": "MP3",
}


def encode(samples: np.ndarray, sample_rate: int, output_format: str) -> tuple[bytes, str]:
    """Return (encoded_bytes, media_type) for a mono float32 signal."""
    fmt = output_format.lower()
    if fmt not in SF_FORMATS:
        raise ValueError(f"unsupported format: {output_format}")

    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format=SF_FORMATS[fmt], subtype=None)
    return buffer.getvalue(), MEDIA_TYPES[fmt]

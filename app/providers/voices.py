"""Voice metadata shared by every provider.

Kept separate from the providers so a client sees identical voice names no
matter which runtime is behind the API.
"""

from __future__ import annotations

# Kokoro v1.0 ships 54 voices. The table is the official voices directory in
# alphabetical order, which is the order sherpa-onnx bakes into voices.bin
# ("the generated v1.0 table contains 54 voices ... existing speaker IDs 0
# through 52 remain unchanged", with em_santa appended at 53).
# Provenance: kokoro-int8-multi-lang-v1_0/README.md in the sherpa-onnx
# tts-models release.
KOKORO_VOICE_IDS: dict[str, int] = {
    name: index
    for index, name in enumerate(
        [
            "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
            "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah",
            "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
            "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice",
            "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable",
            "bm_george", "bm_lewis", "ef_dora", "em_alex", "em_santa",
            "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
            "if_sara", "im_nicola", "jf_alpha", "jf_gongitsune", "jf_nezumi",
            "jf_tebukuro", "jm_kumo", "pf_dora", "pm_alex", "pm_santa",
            "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
            "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
        ]
    )
}

# Accent prefix -> human label. Kokoro encodes accent/gender in the id.
ACCENTS = {"a": "American", "b": "British", "e": "Spanish", "f": "French",
           "h": "Hindi", "i": "Italian", "j": "Japanese", "p": "Portuguese",
           "z": "Chinese"}

VOICE_DESCRIPTIONS: dict[str, str] = {
    "af_heart": "Warm, expressive American female voice.",
    "af_bella": "Soft, breathy American female voice.",
    "af_nicole": "Calm, low American female voice.",
    "af_sarah": "Confident American female voice.",
    "af_sky": "Bright, upbeat American female voice.",
    "am_michael": "Relaxed American male voice.",
    "am_fenrir": "Bold, deep American male voice.",
    "am_puck": "Energetic American male voice.",
    "bf_emma": "Warm British female voice.",
    "bm_george": "Steady British male voice.",
}


def voice_gender(voice_id: str) -> str | None:
    prefix = voice_id[:2]
    if prefix[1:2] == "f":
        return "female"
    if prefix[1:2] == "m":
        return "male"
    return None


def voice_accent(voice_id: str) -> str | None:
    return ACCENTS.get(voice_id[:1])


def voice_display_name(voice_id: str) -> str:
    if voice_id in VOICE_DESCRIPTIONS:
        return voice_id.replace("_", " ").title()
    accent = voice_accent(voice_id) or ""
    gender = voice_gender(voice_id) or ""
    label = " ".join(part for part in (accent, gender) if part)
    return f"{label} voice".title() if label else voice_id

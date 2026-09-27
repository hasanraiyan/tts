"""Resolve Kokoro voice name -> sherpa-onnx speaker id (sid).

Evidence: the bundled voices.bin README says the table is generated from the
official Kokoro-82M/voices directory, IDs 0-52 unchanged, em_santa appended at
53. We assume alphabetical order and then PROVE it by fingerprinting: the same
voice must yield a near-identical waveform through the PyTorch path (loaded by
name) and the ONNX path (loaded by index).
"""

import sys

import numpy as np
import soundfile as sf

TEXT = "The quick brown fox jumps over the lazy dog, then speaks."
OUT = "/tmp/voicecheck"
CANDIDATES = [l.strip() for l in open("/tmp/voice_names.txt") if l.strip()]


def fingerprint(samples, rate, buckets=32):
    """Coarse envelope fingerprint: RMS energy per slice, normalised."""
    a = np.asarray(samples, dtype=np.float32)
    n = max(1, len(a) // buckets)
    trimmed = a[: n * buckets].reshape(buckets, n)
    env = np.sqrt((trimmed.astype(np.float64) ** 2).mean(axis=1)) + 1e-9
    return env / env.max(), rate


def main():
    mode = sys.argv[1]
    if mode == "onnx":
        import os

        import sherpa_onnx

        d = "/models/kokoro-int8-multi-lang-v1_0"
        tts = sherpa_onnx.OfflineTts(
            config=sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                        model=f"{d}/model.int8.onnx",
                        voices=f"{d}/voices.bin",
                        tokens=f"{d}/tokens.txt",
                        lexicon=f"{d}/lexicon-us-en.txt",
                        data_dir=f"{d}/espeak-ng-data",
                        dict_dir=f"{d}/dict",
                        lang="en-us",
                    ),
                    num_threads=1,
                    provider="cpu",
                ),
                rule_fsts="",
                max_num_sentences=1,
            )
        )
        for sid in range(len(CANDIDATES)):
            audio = tts.generate(TEXT, sid=sid, speed=1.0)
            fp, rate = fingerprint(audio.samples, audio.sample_rate)
            sf.write(f"{OUT}_onnx_{sid}.wav", audio.samples, audio.sample_rate)
            print(f"{sid}\t{rate}\t" + ",".join(f"{v:.5f}" for v in fp), flush=True)
        return 0

    # mode == "torch": reference fingerprints, loaded by voice name
    from app.config import get_settings
    from app.providers.kokoro import KokoroProvider

    provider = KokoroProvider(get_settings())
    provider.load()
    for name in CANDIDATES:
        result = provider.synthesize(TEXT, voice=name, language="en", speed=1.0)
        fp, rate = fingerprint(result.samples, result.sample_rate)
        print(f"{name}\t{rate}\t" + ",".join(f"{v:.5f}" for v in fp), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

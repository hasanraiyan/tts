"""Prove whether Kokoro v1.0 (int8 ONNX) fits in 512MB, and resolve voice ids.

Runs inside a container started with --memory=512m. If the OOM killer takes
this process, the approach is not viable.
"""

import os
import resource
import sys
import time

MODEL_DIR = "/models/kokoro-int8-multi-lang-v1_0"


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def cur_mb():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1]) // 1024
    return 0


def main():
    print(f"=== baseline rss={cur_mb()} MB ===", flush=True)
    import sherpa_onnx

    print(f"import sherpa_onnx: rss={cur_mb()} MB", flush=True)

    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=os.path.join(MODEL_DIR, "model.int8.onnx"),
                voices=os.path.join(MODEL_DIR, "voices.bin"),
                tokens=os.path.join(MODEL_DIR, "tokens.txt"),
                lexicon=os.path.join(MODEL_DIR, "lexicon-us-en.txt"),
                data_dir=os.path.join(MODEL_DIR, "espeak-ng-data"),
                dict_dir=os.path.join(MODEL_DIR, "dict"),
                lang="en-us",
            ),
            num_threads=1,
            provider="kokoro",
        ),
        rule_fsts="",
        max_num_sentences=1,
    )

    started = time.perf_counter()
    tts = sherpa_onnx.OfflineTts(config)
    print(f"model loaded in {time.perf_counter() - started:.1f}s "
          f"rss={cur_mb()} MB peak={rss_mb()} MB", flush=True)
    print(f"sample_rate={tts.sample_rate} num_speakers={tts.num_speakers}", flush=True)

    # Is a name->id table available, or must we hardcode one?
    for attr in ("speaker_names", "speakers", "id2speaker", "speaker2id"):
        print(f"  hasattr(tts, {attr!r}) = {hasattr(tts, attr)}", flush=True)
    try:
        meta = sherpa_onnx.OfflineTts.tts_metadata  # noqa: B018
    except Exception:
        pass

    text = (
        "Welcome to the AI text to speech service. "
        "This is a memory constrained smoke test running inside a container."
    )
    for sid in (0, 3, 53):
        started = time.perf_counter()
        audio = tts.generate(text, sid=sid, speed=1.0)
        elapsed = time.perf_counter() - started
        duration = len(audio.samples) / audio.sample_rate
        print(f"sid={sid:2d}: {duration:.2f}s audio in {elapsed:.2f}s "
              f"RTF={elapsed / duration:.2f} rss={cur_mb()} MB peak={rss_mb()} MB", flush=True)

    import soundfile as sf

    audio = tts.generate("The quick brown fox jumps over the lazy dog.", sid=0)
    sf.write("/tmp/out.wav", audio.samples, audio.sample_rate)
    data, sr = sf.read("/tmp/out.wav")
    peak = max(abs(x) for x in data)
    print(f"decode test: {len(data)} samples @ {sr}Hz peak={peak:.3f}", flush=True)
    assert len(data) > 0 and peak > 0.01, "audio invalid"
    print(f"FITS: peak {rss_mb()} MB under the 512MB cap", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

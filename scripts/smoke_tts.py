"""Standalone smoke test: text -> Kokoro -> audio -> decode test.

Verifies the model downloads from Hugging Face, loads, and produces
decodable English audio before any API work is considered done (SRS 42).
"""

import os
import sys
import time
import tempfile

import soundfile as sf


def main() -> int:
    text = (
        "Welcome to the AI text to speech service. "
        "This is a smoke test of English speech generation."
    )
    model_id = os.getenv("MODEL_ID", "hexgrad/Kokoro-82M")
    voice = os.getenv("DEFAULT_VOICE", "af_heart")
    out_path = os.path.join(tempfile.gettempdir(), "kokoro_smoke.wav")

    print(f"[1/4] importing kokoro (model_id={model_id}) ...", flush=True)
    t0 = time.perf_counter()
    from kokoro import KModel, KPipeline

    print(f"[2/4] loading model + downloading from HF cache if needed ...", flush=True)
    model = KModel(repo_id=model_id).to("cpu").eval()
    pipeline = KPipeline(lang_code="a", repo_id=model_id, model=model)
    t_load = time.perf_counter() - t0
    print(f"      model loaded in {t_load:.1f}s", flush=True)

    print("[3/4] generating audio ...", flush=True)
    t1 = time.perf_counter()
    chunks = list(pipeline(text, voice=voice))
    t_gen = time.perf_counter() - t1
    if not chunks:
        print("FAIL: pipeline returned no audio chunks", flush=True)
        return 1
    import numpy as np

    audio = np.concatenate([c.audio for c in chunks])
    sf.write(out_path, audio, 24000)
    dur = len(audio) / 24000
    rtf = t_gen / dur if dur else float("inf")
    print(f"      audio: {dur:.2f}s written to {out_path}", flush=True)
    print(f"      generation: {t_gen:.2f}s  RTF: {rtf:.3f}", flush=True)

    print("[4/4] decode test ...", flush=True)
    data, sr = sf.read(out_path)
    assert len(data) > 0, "empty audio"
    assert sr == 24000, f"unexpected sample rate {sr}"
    peak = float(abs(data).max())
    assert peak > 0.01, f"audio looks silent (peak={peak})"
    print(f"      decoded ok: {len(data)} samples @ {sr}Hz, peak={peak:.3f}", flush=True)
    print("SMOKE TEST PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

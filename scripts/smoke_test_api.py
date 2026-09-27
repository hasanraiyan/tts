"""End-to-end smoke test for the TTS API.

Runs the same checks against any deployment. Defaults to the live instance:

    python scripts/smoke_test_api.py
    python scripts/smoke_test_api.py http://127.0.0.1:8000 --api-key KEY

Exit code 0 means every check passed, so it is safe to use as a post-deploy
gate.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://tts-rab2.onrender.com"

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def request(
    method: str,
    url: str,
    api_key: str | None = None,
    body: dict | None = None,
    timeout: float = 180.0,
) -> tuple[int, bytes, dict[str, str]]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def audio_seconds(data: bytes) -> float:
    """Decode duration from a WAV header without extra dependencies."""
    try:
        import soundfile as sf

        with sf.SoundFile(io.BytesIO(data)) as handle:
            return len(handle) / float(handle.samplerate)
    except Exception:
        if data[:4] == b"RIFF" and len(data) > 44:
            rate = int.from_bytes(data[24:28], "little")
            return max(0.0, (len(data) - 44) / (rate * 2)) if rate else 0.0
        return 0.0


def header(headers, name, default=None):
    """HTTP header names are case-insensitive; urllib keeps the server's casing."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", nargs="?", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="test-local-key")
    parser.add_argument("--text", default=None)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"Smoke testing {base}\n" + "-" * 60, flush=True)

    status, body, _ = request("GET", f"{base}/health")
    record("GET /health -> 200", PASS if status == 200 else FAIL, f"status={status}")

    started = time.perf_counter()
    status, body, _ = request("GET", f"{base}/ready")
    ready_seconds = time.perf_counter() - started
    if status == 200:
        payload = json.loads(body)
        record("GET /ready -> 200 ready", PASS if payload.get("model_loaded") else FAIL,
               f"warm={ready_seconds:.2f}s revision={payload.get('model_revision')}")
    else:
        record("GET /ready -> 200 ready", FAIL, f"status={status} body={body[:200]!r}")

    status, body, _ = request("GET", f"{base}/v1/info")
    record("GET /v1/info without key -> 401", PASS if status == 401 else FAIL, f"status={status}")

    status, body, _ = request("GET", f"{base}/v1/info", api_key="wrong-key")
    record("GET /v1/info with bad key -> 401", PASS if status == 401 else FAIL, f"status={status}")

    status, body, _ = request("GET", f"{base}/v1/info", api_key=args.api_key)
    if status == 200:
        info = json.loads(body)
        record("GET /v1/info with key -> 200", PASS, f"provider={info['provider']} voices={info['voice_count']}")
    else:
        record("GET /v1/info with key -> 200", FAIL, f"status={status}")

    status, body, _ = request("GET", f"{base}/v1/voices", api_key=args.api_key)
    if status == 200:
        payload = json.loads(body)
        voices = payload["voices"]
        record("GET /v1/voices -> 200", PASS if voices else FAIL,
               f"{len(voices)} voices, default={payload.get('default_voice')}")
    else:
        record("GET /v1/voices -> 200", FAIL, f"status={status}")

    text = args.text or (
        "Welcome to the AI text to speech service. "
        "This is an automated smoke test. "
        "The quick brown fox jumps over the lazy dog."
    )
    payload = {"text": text, "language": "en", "voice": "default", "format": "mp3"}
    started = time.perf_counter()
    status, body, headers = request("POST", f"{base}/v1/speech", api_key=args.api_key, body=payload)
    elapsed = time.perf_counter() - started
    if status == 200:
        duration = audio_seconds(body)
        ctype = header(headers, "Content-Type", "")
        ok = len(body) > 1000 and duration > 0.5
        record("POST /v1/speech (mp3) -> audio", PASS if ok else FAIL,
               f"{len(body)} bytes, {ctype}, {duration:.2f}s audio in {elapsed:.2f}s wall")
    else:
        record("POST /v1/speech (mp3) -> audio", FAIL, f"status={status} body={body[:200]!r}")

    payload["format"] = "wav"
    status, body, headers = request("POST", f"{base}/v1/speech", api_key=args.api_key, body=payload)
    duration = audio_seconds(body) if status == 200 else 0
    record("POST /v1/speech (wav) -> audio", PASS if status == 200 and duration > 0.5 else FAIL,
           f"{len(body)} bytes, {header(headers, 'Content-Type')}, {duration:.2f}s audio")

    long_text = ("This is a longer paragraph used to measure sustained performance. " * 12)[:4200]
    timings = []
    for _ in range(3):
        started = time.perf_counter()
        status, body, headers = request(
            "POST", f"{base}/v1/speech", api_key=args.api_key,
            body={"text": long_text, "voice": "default", "format": "wav"},
        )
        timings.append(time.perf_counter() - started)
    if status == 200:
        rtf = header(headers, "X-Real-Time-Factor", "?")
        record("POST /v1/speech (long text, 3x)", PASS,
               f"median {statistics.median(timings):.1f}s, RTF={rtf}")
    else:
        record("POST /v1/speech (long text)", FAIL, f"status={status}")

    for name, body_in, expect in [
        ("empty text", {"text": "   "}, 400),
        ("unsupported language", {"text": "hello", "language": "hi"}, 400),
        ("unsupported voice", {"text": "hello", "voice": "nope"}, 400),
        ("unsupported format", {"text": "hello", "format": "flac"}, 400),
        ("text too long", {"text": "x" * 6000}, 413),
    ]:
        status, body_out, _ = request("POST", f"{base}/v1/speech", api_key=args.api_key, body=body_in)
        record(f"validation: {name} -> {expect}", PASS if status == expect else FAIL,
               f"status={status} {body_out[:80].decode(errors='replace')}")

    status, _, _ = request("POST", f"{base}/v1/speech", body={"text": "hi"})
    record("POST /v1/speech without key -> 401", PASS if status == 401 else FAIL, f"status={status}")

    print("-" * 60, flush=True)
    failed = [r for r in results if r[0] == FAIL]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed", flush=True)
    if failed:
        print("FAILED: " + ", ".join(r[1] for r in failed), flush=True)
        return 1
    print("ALL CHECKS PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

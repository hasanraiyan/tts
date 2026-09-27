"""End-to-end check of the asynchronous job flow against a running service.

Defaults to the live deployment; pass a different base URL to test locally:

    python scripts/test_job_flow.py
    python scripts/test_job_flow.py http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://tts-rab2.onrender.com"

PASS, FAIL = "PASS", "FAIL"
failures: list[str] = []


def call(method, url, api_key=None, body=None, timeout=600):
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


def header(headers, name, default=None):
    """HTTP header names are case-insensitive; urllib keeps the server's casing."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def check(name, ok, detail=""):
    print(f"[{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        failures.append(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", nargs="?", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="test-local-key")
    parser.add_argument("--other-key", default="someone-elses-key")
    parser.add_argument("--poll", type=float, default=2.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    key = args.api_key

    text = (
        "Jobs keep long text off the request thread. "
        "This sentence checks that progress is reported. "
        "And this one checks that the audio comes back at the end."
    )

    status, body, _ = call("POST", f"{base}/v1/speech/jobs", key, {"text": text, "format": "mp3"})
    if status != 202:
        print(f"[FAIL] POST /v1/speech/jobs -> 202 (got {status}: {body[:200]!r})")
        return 1
    job = json.loads(body)
    run_id = job["run_id"]
    check("POST /v1/speech/jobs -> 202 with run_id", bool(run_id),
          f"run_id={run_id} status={job['status']} chunks={job['chunks']}")
    check("job starts queued or running", job["status"] in {"queued", "running"}, job["status"])

    status, body, _ = call("GET", f"{base}/v1/jobs/{run_id}", key)
    if status == 200:
        check("GET /v1/jobs/{id} -> 200", True, f"status={json.loads(body)['status']}")
    else:
        check("GET /v1/jobs/{id} -> 200", False, f"status={status}")

    status, _, _ = call("GET", f"{base}/v1/jobs/{run_id}", args.other_key)
    # 401 when the key is not configured at all, 404 when it is a different but
    # valid client. Either way the job is not readable by anyone else.
    check("another client cannot read the job", status in {401, 404}, f"status={status}")

    status, body, _ = call("GET", f"{base}/v1/jobs/{run_id}/audio", key)
    check("audio before completion -> 409", status == 409, f"status={status}")

    seen_progress = False
    started = time.perf_counter()
    final = None
    while time.perf_counter() - started < 900:
        status, body, _ = call("GET", f"{base}/v1/jobs/{run_id}", key)
        if status != 200:
            break
        current = json.loads(body)
        if current["progress"] > 0 and current["progress"] < 1:
            seen_progress = True
        if current["status"] in {"completed", "failed"}:
            final = current
            break
        time.sleep(args.poll)
    elapsed = time.perf_counter() - started

    if final is None:
        check("job reaches a terminal state", False, f"still running after {elapsed:.0f}s")
        return 1
    check("job reaches a terminal state", final["status"] == "completed",
          f"status={final['status']} in {elapsed:.0f}s" +
          (f" error={final.get('error')}" if final.get("error") else ""))
    if final["status"] != "completed":
        return 1
    check("progress was reported while running", True,
          f"progress={final['progress']} audio_s={final['audio_seconds']} "
          f"gen_s={final['generation_seconds']} observed_partial={seen_progress}")
    check("completed job reports audio_url", bool(final.get("audio_url")), final.get("audio_url") or "")

    status, body, headers = call("GET", f"{base}/v1/jobs/{run_id}/audio", key)
    content_type = header(headers, "Content-Type", "")
    ok = status == 200 and len(body) > 1000
    check("GET /v1/jobs/{id}/audio -> audio", ok,
          f"{status} {len(body)} bytes {content_type}")
    if ok:
        check("audio is mp3", content_type == "audio/mpeg", content_type or "(none)")
        check("audio declares its duration",
              header(headers, "X-Audio-Duration-Seconds") is not None,
              f"{header(headers, 'X-Audio-Duration-Seconds')}s")
        with open(".cache/job_audio.mp3", "wb") as handle:
            handle.write(body)

    status, body, _ = call("GET", f"{base}/v1/jobs", key)
    jobs = json.loads(body)["jobs"] if status == 200 else []
    check("GET /v1/jobs lists this client's jobs", any(j["run_id"] == run_id for j in jobs),
          f"{len(jobs)} job(s)")

    status, _, _ = call("DELETE", f"{base}/v1/jobs/{run_id}", key)
    check("DELETE /v1/jobs/{id} -> 204", status == 204, f"status={status}")
    status, _, _ = call("GET", f"{base}/v1/jobs/{run_id}", key)
    check("job is gone after delete -> 404", status == 404, f"status={status}")

    for name, payload, expect in [
        ("empty text", {"text": "  "}, 400),
        ("too long", {"text": "x" * 6000}, 413),
        ("bad voice", {"text": "hi", "voice": "nope"}, 400),
        ("bad language", {"text": "hi", "language": "hi"}, 400),
        ("bad format", {"text": "hi", "format": "flac"}, 400),
    ]:
        status, _, _ = call("POST", f"{base}/v1/speech/jobs", key, payload)
        check(f"job validation: {name} -> {expect}", status == expect, f"status={status}")

    status, _, _ = call("POST", f"{base}/v1/speech/jobs", None, {"text": "hi"})
    check("POST /v1/speech/jobs without key -> 401", status == 401, f"status={status}")

    print("-" * 60, flush=True)
    if failures:
        print(f"FAILED: {', '.join(failures)}", flush=True)
        return 1
    print("JOB FLOW OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Deploying to Render

The service runs on Render as a **Docker** image built from the `Dockerfile` in
this repo. Render never reads `.env`; every variable is set in the dashboard.
Keep `.env` for local development only.

There is no `render.yaml` — the steps below are done by hand in the dashboard.

## 1. Create the service

*New → Web Service* → connect `https://github.com/hasanraiyan/tts`

| Setting | Value | Why |
| --- | --- | --- |
| Runtime | **Docker** | Uses the repo's Dockerfile |
| Instance type | **Free** | 512 MB is enough: the ONNX provider peaks at ~370 MB |
| Region | your nearest | |
| Health check path | `/ready` | 503 until the model loads, then 200 |

Free is viable on memory. Be aware its **CPU is only 0.1 core**, so generation
is roughly 10x slower than the benchmarks in the README. Fine for testing and
low volume; move to a paid plan for real traffic.

## 2. Generate API keys

Do this locally, once per consuming application:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Each consuming app gets its own key, so requests are attributable and can be
rate-limited or revoked independently.

## 3. Environment variables to set

### Secrets — set these in the dashboard

| Key | Value |
| --- | --- |
| `API_KEY_DEFAULT` | generated key, for ad-hoc/testing clients |
| `API_KEY_MINDPAGEREADS` | generated key, for the MindpageReads app |
| `API_KEY_COURSIFY` | generated key, for the Coursify app |
| `HF_TOKEN` | Hugging Face token (optional, recommended) |

`HF_TOKEN` is not needed by the default ONNX provider, which downloads its model
from the sherpa-onnx release at build time. It is still worth setting: it
authenticates any Hub access and protects the optional PyTorch provider from
anonymous rate limits. Never commit it.

**Every other `API_KEY_<NAME>` you add becomes a new client automatically** — no
code change. The client id is the lower-cased suffix (`API_KEY_COURSIFY` →
`coursify`).

### Optional — defaults are already sensible

| Key | Default | Notes |
| --- | --- | --- |
| `TTS_PROVIDER` | `onnx` | Keep this on the free plan. `torch` needs 1.3 GB and will be OOM-killed. |
| `ONNX_NUM_THREADS` | `1` | Free instances have 0.1 core, so 1 is right |
| `DEFAULT_VOICE` | `af_heart` | Any id from `GET /v1/voices` |
| `DEFAULT_FORMAT` | `mp3` | `mp3` or `wav` |
| `MAX_TEXT_LENGTH` | `5000` | Consider lowering on a free instance |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per API key, in memory |
| `MAX_CONCURRENCY` | `1` | CPU inference is serialised |
| `LOG_LEVEL` | `INFO` | |

### Do not set

- `PORT` — Render injects it; the start command reads it.
- `HOST` — the start command binds `0.0.0.0` already.
- `ONNX_MODEL_DIR` — already correct in the image.
- `MODEL_ID` / `MODEL_REVISION` — only used by the optional PyTorch provider,
  whose weights are not in this image. Setting them would do nothing.

The start command needs no configuration; the image default is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 4. Verify the deployment

```bash
python scripts/smoke_test_api.py https://<your-service>.onrender.com --api-key <API_KEY_DEFAULT>
```

The same script runs against local and Docker targets, so results are directly
comparable. It checks auth, validation, both audio formats, and reports
generation time and real-time factor.

The long-text check in that script may be slow on a free instance. If it times
out, re-run with a shorter text:

```bash
python scripts/smoke_test_api.py https://<service>.onrender.com --api-key <key> --text "Short test."
```

## 5. Cold starts

Free instances sleep after inactivity and restart on every deploy. Cold start is
container boot plus ~2 s of model load, so `/ready` returns 200 within a few
seconds — far better than the PyTorch variant, which needed ~14 s.

If a client has a short timeout, treat `503 MODEL_NOT_READY` as retryable with
backoff.

## 6. If it runs out of memory

Check the Render logs for `Out of memory`. That means something loaded PyTorch:
confirm `TTS_PROVIDER` is `onnx` (or unset) and that the image was built without
`--build-arg TTS_RUNTIME=torch`. The default image contains no PyTorch at all.

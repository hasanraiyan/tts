# AI TTS Service

A generic, reusable **text-to-speech API**. Any application authenticates with
its own API key and posts text; the service returns audio. The client never
needs to know which model is behind the API.

```
MindpageReads ─┐
Coursify ──────┼──►  AI TTS Service  ──►  TTS provider  ──►  audio
OnlyFounders ──┘         (FastAPI)          (Kokoro)
```

- **Model:** Kokoro v1.0 (`hexgrad/Kokoro-82M`), 82M params, Apache-2.0
- **Language:** English (Kokoro supports more; see [Extending](#extending))
- **Output:** MP3 or WAV, 24 kHz mono
- **Runtime:** CPU only, no GPU, no ffmpeg binary
- **Deploys to:** local, Docker, Render

> The design rule that matters: **clients talk to a TTS API, not to Kokoro.**
> Replacing the model must not require any client change — that is why all
> model code lives behind `app/providers/base.py`.

---

## Quick start (local)

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
.\.venv\Scripts\pip.exe python -c "import spacy; spacy.load('en_core_web_sm')"   # one-time
Copy-Item .env.example .env    # then set API_KEY=...
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Configuration comes from environment variables; `.env` is loaded automatically
in development. **Never commit `.env`.**

First start downloads the model (~340 MB) into `HF_HOME` and takes ~30 s.
Every later start is ~14 s from cache. Verify with:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test_api.py http://127.0.0.1:8000 --api-key <your key>
```

---

## API

Base URL: `http://127.0.0.1:8000` locally. Interactive docs at `/docs`, schema at
`/openapi.json`.

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | no | Liveness. Always 200 while the process is up. |
| GET | `/ready` | no | Model readiness. 200 when audio can be generated, else 503. |
| GET | `/v1/info` | yes | Provider, model revision, limits, formats. |
| GET | `/v1/voices` | yes | Available voice ids. |
| POST | `/v1/speech` | yes | Generate speech. |

### Generate speech

```bash
curl -X POST http://127.0.0.1:8000/v1/speech \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"The most important thing is to focus on one task at a time.",
       "language":"en","voice":"default","format":"mp3"}' \
  --output speech.mp3
```

Request fields — only `text` is required:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `text` | string | — | 1 to `MAX_TEXT_LENGTH` (5000) characters |
| `language` | string | `en` | Only `en` today; others return 400 |
| `voice` | string | `default` | `default` (i.e. `af_heart`) or any id from `/v1/voices` |
| `format` | string | `mp3` | `mp3` or `wav` |
| `speed` | float | `1.0` | 0.5 – 2.0 |

Response is raw audio (`audio/mpeg` or `audio/wav`) with useful timing headers:

```
X-Audio-Duration-Seconds: 5.950   how much audio you got
X-Generation-Seconds:     8.925   time spent synthesising it
X-Server-Seconds:         9.140   total, including encoding
X-Real-Time-Factor:       1.500   generation / duration (<1 is faster than realtime)
X-Voice: af_heart   X-Language: en   X-Provider: kokoro
```

### Errors

Always JSON, never a stack trace:

```json
{ "error": "TEXT_TOO_LONG", "message": "Text exceeds the maximum allowed length of 5000 characters." }
```

| Code | Status | Cause |
| --- | --- | --- |
| `UNAUTHORIZED` | 401 | Missing, malformed or unknown API key |
| `INVALID_REQUEST` | 400 | Bad JSON, wrong field type, empty text |
| `TEXT_TOO_LONG` | 413 | Over `MAX_TEXT_LENGTH` |
| `UNSUPPORTED_LANGUAGE` | 400 | Language not enabled |
| `UNSUPPORTED_VOICE` | 400 | Voice id not in `/v1/voices` |
| `UNSUPPORTED_FORMAT` | 400 | Format not in `SUPPORTED_FORMATS` |
| `RATE_LIMITED` | 429 | Over `RATE_LIMIT_PER_MINUTE` (has `Retry-After`) |
| `MODEL_NOT_READY` | 503 | Model still loading or failed to load |
| `SERVER_BUSY` | 503 | Queue timeout while waiting for the model |
| `TTS_GENERATION_FAILED` | 500 | Synthesis raised |
| `INTERNAL_ERROR` | 500 | Anything unexpected |

---

## Authentication

Every `API_KEY_<NAME>` environment variable becomes a client. The suffix is the
client id, and it is how usage is attributed in the logs:

```env
API_KEY_MINDPAGEREADS=<32+ random bytes>
API_KEY_COURSIFY=<32+ random bytes>
API_KEY_DEFAULT=<32+ random bytes>   # optional catch-all
```

Onboarding an application is therefore **one environment variable and no code
change**. Keys are compared in constant time; the key itself is never logged
or returned. Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Configuration

Every variable, its default, and what it does. All are optional unless noted.

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_KEY_<NAME>` | — | **Required for any `/v1/*` call.** One per client. |
| `HF_TOKEN` | unset | Hugging Face token. Optional for the public Kokoro repo; set it to avoid anonymous rate limits. |
| `HF_HOME` | `~/.cache/huggingface` | Model cache location. Baked to `/app/.cache/huggingface` in the image. |
| `MODEL_ID` | `hexgrad/Kokoro-82M` | Model repo. Only used by the `torch` provider. |
| `TTS_PROVIDER` | `onnx` | `onnx` (370MB, fits free tier) or `torch` (fp32, needs 1.3GB) |
| `ONNX_MODEL_DIR` | `/app/models/kokoro-int8-multi-lang-v1_0` | Where the ONNX model lives |
| `ONNX_NUM_THREADS` | `1` | CPU threads for ONNX inference |
| `MODEL_REVISION` | `f3ff3571…b4987` | **Pinned commit.** Guarantees identical weights everywhere. |
| `MODEL_WEIGHTS_FILE` | `kokoro-v1_0.pth` | Which weight file to load. |
| `DEFAULT_LANGUAGE` | `en` | Language used when the request omits one |
| `DEFAULT_VOICE` | `af_heart` | Voice used for `"voice":"default"` |
| `DEFAULT_FORMAT` | `mp3` | Format used when the request omits one |
| `SUPPORTED_FORMATS` | `mp3,wav` | Formats accepted from clients |
| `MAX_TEXT_LENGTH` | `5000` | Per-request character cap |
| `SAMPLE_RATE` | `24000` | Output sample rate |
| `DEFAULT_SPEED` | `1.0` | Default speaking rate |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per client, per minute, in memory |
| `MAX_CONCURRENCY` | `1` | Simultaneous generations; extra requests queue |
| `QUEUE_TIMEOUT_SECONDS` | `120` | Wait time before `SERVER_BUSY` |
| `TORCH_NUM_THREADS` | `4` | CPU threads for inference |
| `PRELOAD_MODEL` | `true` | Load at startup instead of on first request |
| `APP_ENV` | `production` | Free-form environment label |
| `LOG_LEVEL` | `INFO` | Python log level |
| `PORT` | `8000` | Injected by Render; local default only |
| `HOST` | `0.0.0.0` | Bind address |

Set `PRELOAD_MODEL=false` to let the process boot instantly and load the model
on the first request; `/ready` stays 503 until then.

---

## Performance

Measured on this repository's Docker image, CPU only, 1 inference thread. The
ONNX row is the default; the PyTorch row is kept for quality comparisons.

| Metric | **ONNX (default)** | PyTorch (optional) |
| --- | --- | --- |
| **Peak memory** | **~370 MB** | ~1.25–1.40 GB |
| Steady memory after load | ~355 MB | ~1.07 GB |
| Model load from cache | **1.9 s** | ~14 s |
| Model on disk | 183 MB | 340 MB |
| Runtime import cost | 25 MB | 274 MB (torch + spacy) |
| Real-time factor, 1 thread | ~1.5–1.9 | ~1.5 |
| Real-time factor, 4 threads | — | ~0.7 (16-thread desktop) |
| Image size | ~0.9 GB | ~3.6 GB |

Both providers run the same Apache-2.0 Kokoro v1.0 weights; the ONNX build is
int8-quantised, which is where the memory and size savings come from.

**Why there are two providers.** PyTorch cannot run in 512 MB and there is no
flag that changes that: `import torch` plus `spacy` costs 274 MB before any
inference, and the fp32 weights are 327 MB. Memory-mapping them was measured and
did not help (identical 1249 MB peak, ~2x slower synthesis), so the fix had to
be a lighter runtime, not a tuned one. ONNX peaks at 370 MB, verified inside a
container hard-capped with `--memory=512m`, which is why the service defaults to
it and runs on Render's free plan.

Switch between them with `TTS_PROVIDER=onnx|torch`. Clients cannot tell the
difference — same endpoints, same voices, same response headers.

### The real limit on the free plan

Memory is solved; **CPU is not**. Render's free plan is 512 MB but only 0.1
core, and the measurements above are from a full core. Expect real-time factor
to degrade roughly 10x, i.e. a 60-second passage may take several minutes, and
`MAX_TEXT_LENGTH=5000` is far more text than a free instance should be asked
for at once. For production traffic use a paid plan; for testing and low volume
the free plan is fine. If you raise `MAX_TEXT_LENGTH` awareness to users, pair
it with client-side timeouts and retries on `503 SERVER_BUSY`.

Reproduce the memory numbers:

```powershell
docker run --rm --memory=512m -p 8010:8000 -e API_KEY=test ai-tts-service:latest
python scripts/smoke_test_api.py http://127.0.0.1:8010 --api-key test
docker stats ai-tts-service          # watch MEM USAGE
```

---

## Docker

```powershell
docker build -t ai-tts-service:latest .
docker run --rm -p 8000:8000 -e API_KEY=test ai-tts-service:latest
```

The default image contains **no PyTorch at all** — just sherpa-onnx and the
int8 Kokoro model baked in, so it is ~0.9 GB instead of ~3.6 GB and cold starts
never wait on a download. It runs as a non-root user, and `HEALTHCHECK` hits
`/ready`, so a container whose model failed to load is reported unhealthy
rather than silently serving broken audio.

To build the fp32 PyTorch variant instead:

```powershell
docker build --build-arg TTS_RUNTIME=torch -t ai-tts-service:torch .
```

That variant needs ~1.3 GB of RAM, so it cannot run on Render's 512 MB plans.

## Render

See **[RENDER.md](RENDER.md)** for the step-by-step dashboard setup. Short
version: create a Web Service from this repo with Runtime **Docker** and plan
**Free**, then set four secrets (`API_KEY_DEFAULT`, `API_KEY_MINDPAGEREADS`,
`API_KEY_COURSIFY`, `HF_TOKEN`) and deploy. Then:

```bash
python scripts/smoke_test_api.py https://<service>.onrender.com --api-key <key>
```

---

## Layout

```
app/
├── main.py              FastAPI app, lifespan, error handlers, logging
├── config.py            env-driven Settings; API_KEY_* collection
├── state.py             runtime holder (provider + service + readiness)
├── errors.py            structured error codes
├── logging_config.py    logging that can never leak keys or text
├── api/
│   ├── routes.py        the five endpoints
│   ├── dependencies.py  Bearer auth, client identity, rate limiting
│   └── schemas.py       request/response models (drive /docs)
├── providers/
│   ├── base.py          TTSProvider ABC — the only contract the API knows
│   ├── voices.py        shared voice names + name→speaker-id table
│   ├── onnx.py          default: Kokoro v1.0 int8 via sherpa-onnx (370MB)
│   └── kokoro.py        optional: Kokoro v1.0 fp32 via PyTorch (1.3GB)
└── services/
    ├── tts.py           queueing + provider invocation
    ├── audio.py         numpy → mp3/wav via libsndfile
    └── rate_limit.py    per-client sliding window

scripts/
├── smoke_tts.py         text → audio → decode, no API involved
├── smoke_test_api.py    full end-to-end check against any base URL
├── probe_onnx_memory.py measures whether the model fits a memory cap
└── resolve_voice_ids.py proves the voice name→id mapping across providers
```

### Extending

**Another voice:** set `DEFAULT_VOICE`, or pass any of the 54 Kokoro voices per
request. Both providers pre-load voices at startup, so no request touches the
network. ONNX addresses voices by integer id, PyTorch by file name; the mapping
lives in `app/providers/voices.py` so both agree.

**Another language:** add the language to the provider's `list_languages()` and
load a pipeline for it. Kokoro ships Japanese (`j`) and Mandarin (`z`) pipelines;
other languages route through the espeak fallback, which is lower quality.

**Another model:** implement `TTSProvider` (`load`, `list_voices`,
`synthesize`, `supports_language`, `supports_voice`, `model_info`) in a new file
under `app/providers/`, then construct it in `app/state.py`. No route, schema or
auth change — clients cannot tell.

---

## Security

- Secrets live only in environment variables; `.env` is gitignored and
  excluded from the Docker build context.
- API keys are compared in constant time and are never logged or echoed.
- `HF_TOKEN` is read from the environment and never baked into the image.
- Request text is never written to logs — only character counts, so user content
  cannot leak. Timing/usage metadata is logged instead.
- Text length, format, language and voice are all validated before any work.
- Per-client rate limiting plus a concurrency queue protect the CPU.
- Clients never receive stack traces or internal messages.

## Testing

```powershell
.\.venv\Scripts\pytest -q                              # unit/API tests
.\.venv\Scripts\python.exe scripts\smoke_test_api.py http://127.0.0.1:8000 --api-key <key>
```

`smoke_test_api.py` exits non-zero on any failure, so it works as a post-deploy
gate, and it runs identically against local, Docker and Render targets.

## Roadmap

- [x] Kokoro English, local + Docker + Render
- [ ] Web dashboard: sign up / log in, self-service API key creation and
      revocation (keeps keys out of hand-managed environment variables)
- [ ] Usage analytics per client
- [ ] More languages and long-form/streaming generation

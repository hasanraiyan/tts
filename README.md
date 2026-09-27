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
| `MODEL_ID` | `hexgrad/Kokoro-82M` | Model repo. Baked into the image; see render.yaml. |
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

Measured on this repository's Docker image (`ai-tts-service`), CPU only. The
generation figures are for a 6 s sentence on one thread.

| Metric | Value |
| --- | --- |
| Model download (cold) | ~340 MB, ~90 s first ever, then cached |
| Model load from cache | ~14 s |
| Resident memory after load | ~1.07 GB |
| **Peak memory during generation** | **~1.25–1.40 GB** |
| Import cost (torch + spacy) | ~274 MB |
| Kokoro weights | ~327 MB |
| Real-time factor, 1 thread | ~1.5 (6 s audio in ~9 s) |
| Real-time factor, 4 threads | ~0.7 on a 16-thread desktop CPU |

Where the memory goes, and why it cannot simply be trimmed:

- `torch` + `spacy` imports alone are ~274 MB.
- The 327 MB of weights are resident while the model is being built, so peak
  exceeds the steady state.
- mmap-loading the weights was measured and did **not** reduce peak (1249 MB
  both ways) while roughly doubling synthesis time, so it is not used.

**Consequence: Render must be the 2 GB plan.** Both the free (512 MB) and
Starter (512 MB, more CPU) plans are killed by the OOM killer during model
load. `render.yaml` therefore pins `plan: standard`. This is the single most
important operational fact about this service.

If a 512 MB instance is ever a hard requirement, the realistic path is an ONNX
runtime (sherpa-onnx) instead of PyTorch, which trades some quality for roughly
half the memory. The provider abstraction exists to make that swap possible
without touching the API.

Reproduce the numbers:

```powershell
docker run --rm -p 8010:8000 -e API_KEY=test ai-tts-service:latest
python scripts/smoke_test_api.py http://127.0.0.1:8010 --api-key test
```

---

## Docker

```powershell
docker build -t ai-tts-service:latest .
docker run --rm -p 8000:8000 -e API_KEY=test ai-tts-service:latest
```

The image is CPU-only PyTorch (the default PyPI Linux wheel would drag in ~2 GB
of unusable CUDA libraries), runs as a non-root user, and has the model weights
baked in at the pinned revision so cold starts never re-download. `HEALTHCHECK`
hits `/ready`, so a container whose model failed to load is reported unhealthy
rather than silently serving broken audio.

`MODEL_ID` / `MODEL_REVISION` are deliberately **not** set on Render: the image
is the single source of truth, and letting the runtime disagree with the cached
weights would force a re-download on every cold start.

## Render

See **[RENDER.md](RENDER.md)** for the deploy steps and the exact environment
variables. Short version: Blueprint deploy, set the four secrets
(`API_KEY_DEFAULT`, `API_KEY_MINDPAGEREADS`, `API_KEY_COURSIFY`, `HF_TOKEN`),
plan **standard**, then:

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
│   └── kokoro.py        all Kokoro/HF-specific code lives here
└── services/
    ├── tts.py           queueing + provider invocation
    ├── audio.py         numpy → mp3/wav via libsndfile
    └── rate_limit.py    per-client sliding window

scripts/
├── smoke_tts.py         text → audio → decode, no API involved
└── smoke_test_api.py    full end-to-end check against any base URL
```

### Extending

**Another voice:** set `DEFAULT_VOICE`, or pass any of the 54 Kokoro voices per
request. Voices are pre-loaded at startup, so no request touches the network.

**Another language:** add a mapping in `app/providers/kokoro.py`
(`LANG_CODE_BY_LANGUAGE`) and build a pipeline for it. Kokoro ships Japanese
(`j`) and Mandarin (`z`) pipelines; other languages route through the espeak
fallback, which is lower quality.

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

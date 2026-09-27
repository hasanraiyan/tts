# Deploying to Render

The service runs on Render as a **Docker** image (`Dockerfile` in the repo root).
Render never reads `.env`; every variable is set in the dashboard or declared in
`render.yaml`. Keep `.env` for local development only.

## 1. Create the service

Either:

- **Blueprint:** push the repo, click *New → Blueprint*, select this repo.
  `render.yaml` creates the service with everything except the secrets.
- **Manual:** *New → Web Service* → connect `https://github.com/hasanraiyan/tts`
  → Runtime: **Docker** → Plan: **Starter** (1 GB; the free 512 MB tier is too small).

Region and plan are set in `render.yaml` (`singapore`, `starter`).

## 2. Generate API keys

Do this locally, once per consuming application:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Each consuming app gets its own key, so requests are attributable and can be
rate-limited or revoked independently.

## 3. Environment variables to set

### Secrets — you must set these (dashboard prompts for them on first deploy)

| Key | Value |
| --- | --- |
| `API_KEY_DEFAULT` | generated key, for ad-hoc/testing clients |
| `API_KEY_MINDPAGEREADS` | generated key, for the MindpageReads app |
| `API_KEY_COURSIFY` | generated key, for the Coursify app |
| `HF_TOKEN` | Hugging Face token (optional but recommended) |

`HF_TOKEN` is not needed for `hexgrad/Kokoro-82M` because it is a public repo.
Set it anyway: anonymous Hub requests have lower rate limits, so a cold deploy
can be throttled. Never commit it.

**Every other `API_KEY_<NAME>` you add becomes a new client automatically** —
no code change. The client id is the lower-cased suffix (`API_KEY_COURSIFY`
→ `cse`-style id `coursify`).

### Optional — change from the defaults if needed

| Key | Default | Notes |
| --- | --- | --- |
| `MODEL_ID` | `hexgrad/Kokoro-82M` | Weights are baked into the image at this repo |
| `MODEL_REVISION` | `f3ff3571791e39611d31c381e3a41a3af07b4987` | Pinned for reproducibility |
| `DEFAULT_VOICE` | `af_heart` | Any id from `GET /v1/voices` |
| `DEFAULT_FORMAT` | `mp3` | `mp3` or `wav` |
| `MAX_TEXT_LENGTH` | `5000` | Per-request character cap |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per API key, in memory |
| `MAX_CONCURRENCY` | `1` | CPU inference is serialised |
| `TORCH_NUM_THREADS` | `4` | Match the instance's CPU count |
| `LOG_LEVEL` | `INFO` | |

### Do not set

- `PORT` — Render injects it; the start command reads it.
- `HOST` — the start command binds `0.0.0.0` already.
- `HF_HOME` — already set in the `Dockerfile`.

## 4. Health check and start command

- Health check path: `/ready` (503 until the model is loaded, 200 after).
  Render waits for this before routing traffic. If the model ever fails to load,
  the deploy fails loudly instead of serving broken audio.
- Start command (already the image default, no change needed):

  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

## 5. Verify the deployment

```bash
python scripts/smoke_test_api.py https://<your-service>.onrender.com --api-key <API_KEY_DEFAULT>
```

The same script runs against local and Docker targets, so it is a fair
comparison. It checks auth, validation, both audio formats and reports
generation time and real-time factor.

Expect the **first** request after deploy to be slow: the container's first
`/v1/speech` may pay for lazily-imported libraries. The model itself is already
in the image, so startup is a few seconds.

## 6. First-request latency after a cold start

Render free/starter instances sleep after inactivity and can restart on deploy.
Cold start = container start + model load from the image (~15-30 s) before
`/ready` returns 200. If your client has a 10 s timeout, either warm the service
with a health-check ping or accept `MODEL_NOT_READY` (503) and retry with
backoff.

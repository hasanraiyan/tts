# SRS — Generic AI Text-to-Speech Service

**Project:** `ai-tts-service`
**Version:** 1.0 — MVP
**Technology:** Python + FastAPI
**Initial TTS Model:** Kokoro
**Initial Language:** English
**Deployment:** Render
**Model Source:** Hugging Face
**Primary Consumers:** Multiple internal applications

---

# 1. Introduction

## 1.1 Purpose

The purpose of this project is to develop a **reusable Text-to-Speech (TTS) microservice** that provides speech-generation capabilities through a secure REST API.

The service must be independent of any specific application.

For example:

```text
MindpageReads ───────┐
                     │
Coursify ────────────┤
                     │
OnlyFounders ────────┤
                     ▼
               AI TTS Service
                     │
                     ▼
                  TTS Model
```

The first implementation will use **Kokoro for English TTS**, but the architecture must allow the TTS provider/model to be replaced in the future without changing the public API.

Kokoro is an open-weight 82M-parameter TTS model and can be deployed in production or personal projects under its Apache license. ([Hugging Face][2])

---

# 2. Goals

The system must:

1. Generate speech from text.
2. Provide speech generation through a REST API.
3. Authenticate applications using API keys.
4. Support multiple consuming applications.
5. Support multiple API keys.
6. Keep TTS implementation independent from client applications.
7. Download/load the TTS model automatically.
8. Use Hugging Face authentication through environment variables.
9. Cache the downloaded model.
10. Provide audio in a standard format such as MP3/WAV.
11. Provide API documentation.
12. Be deployable on Render.
13. Be easy to replace with another TTS model later.

---

# 3. Non-Goals

The MVP must **not** implement:

* User registration
* User login
* User profiles
* Payments
* Subscription management
* Book management
* Book summarization
* LLM generation
* Notifications
* Scheduling
* Mobile application
* Web dashboard
* Voice cloning
* Hindi TTS
* Hinglish TTS

Those belong to consuming applications or future versions.

---

# 4. High-Level Architecture

```text
                    ┌──────────────────┐
                    │   Client Apps    │
                    │                  │
                    │ MindpageReads    │
                    │ Coursify         │
                    │ Other Projects   │
                    └────────┬─────────┘
                             │
                             │ HTTPS
                             │ API Key
                             ▼
                  ┌──────────────────────┐
                  │    AI TTS SERVICE    │
                  │                      │
                  │ FastAPI              │
                  │ Authentication       │
                  │ Validation           │
                  │ Rate Limiting        │
                  │ TTS Provider Layer   │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    TTS Provider      │
                  │                      │
                  │      Kokoro          │
                  └──────────┬───────────┘
                             │
                             ▼
                         Audio File
```

---

# 5. Technology Stack

## Backend

* Python 3.11/3.12 preferred
* FastAPI
* Uvicorn
* Pydantic

## TTS

Initial provider:

```text
Kokoro
```

The exact package/model version must be pinned and documented.

## Model Hosting

Hugging Face Hub.

## Deployment

Render.

## Containerization

Docker is preferred for reproducible deployment.

---

# 6. Functional Requirements

## FR-001 — Health Check

The service must provide:

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

This endpoint should not require authentication.

---

# 7. Speech Generation

## FR-002 — Generate Speech

The API must provide:

```http
POST /v1/speech
```

Request:

```json
{
  "text": "Welcome to MindpageReads. Today we are going to learn something interesting.",
  "language": "en",
  "voice": "default",
  "format": "mp3"
}
```

Response:

```http
Content-Type: audio/mpeg
```

The response body should contain the generated audio.

---

# 8. API Authentication

## FR-003 — API Key Authentication

All protected endpoints must require:

```http
Authorization: Bearer <API_KEY>
```

Example:

```http
Authorization: Bearer abc123...
```

Invalid API keys must return:

```http
401 Unauthorized
```

Example:

```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid API key."
}
```

---

# 9. Multiple Applications

The service must support multiple API keys.

Example:

```text
MindpageReads → API_KEY_1
Coursify      → API_KEY_2
OnlyFounders  → API_KEY_3
```

The implementation must identify which client is making the request.

This will allow future usage tracking.

---

# 10. API Key Security

API keys must:

* Never be committed to Git.
* Never appear in source code.
* Never appear in application logs.
* Never be returned through an API.
* Be stored securely as environment variables or a secure configuration system.

For the MVP, keys may be configured through environment variables.

---

# 11. Text Validation

## FR-004

The service must validate incoming text.

Reject:

* Empty text
* Null text
* Excessively long text
* Invalid request bodies
* Unsupported languages
* Unsupported voices
* Unsupported formats

Example:

```json
{
  "error": "TEXT_TOO_LONG",
  "message": "Text exceeds the maximum allowed length."
}
```

The maximum text length must be configurable.

Example:

```env
MAX_TEXT_LENGTH=5000
```

---

# 12. Language Support

## FR-005

The API must accept a language field:

```json
{
  "language": "en"
}
```

For MVP:

```text
en → Supported
hi → Not supported
```

Unsupported languages should return:

```http
400 Bad Request
```

rather than attempting generation.

The architecture must allow Hindi or other languages to be added later.

---

# 13. Voice Support

## FR-006

The API must support a voice parameter:

```json
{
  "voice": "default"
}
```

For MVP, at least one English voice must be available.

---

# 14. Voice Discovery

## FR-007

Provide:

```http
GET /v1/voices
```

Example:

```json
{
  "voices": [
    {
      "id": "default",
      "name": "Default English",
      "language": "en"
    }
  ]
}
```

This prevents client applications from hardcoding voice information.

---

# 15. Audio Formats

## FR-008

The service should support:

```text
mp3
wav
```

If the underlying model doesn't natively generate one format, the service may convert the generated audio.

The supported formats must be documented through the API.

---

# 16. TTS Provider Abstraction

This is a **mandatory architectural requirement**.

The API must not directly depend on Kokoro implementation details.

Use an abstraction such as:

```python
class TTSProvider:
    def generate(
        self,
        text: str,
        language: str,
        voice: str,
        output_format: str
    ):
        ...
```

Then:

```text
providers/
├── base.py
└── kokoro.py
```

Future providers can be added:

```text
providers/
├── base.py
├── kokoro.py
├── provider_x.py
└── provider_y.py
```

The API remains unchanged.

---

# 17. Model Management

## FR-009 — Hugging Face Authentication

The service must use the Hugging Face token through:

```env
HF_TOKEN=your_huggingface_token
```

Do **not** hardcode the token.

Hugging Face officially supports `HF_TOKEN` for Hub authentication. ([Hugging Face][1])

If the model is public and does not require authentication, the service may still support `HF_TOKEN` for consistency and future private/gated models.

---

# 18. Model Download

The service must download the model from Hugging Face automatically during setup/startup as appropriate.

The implementation may use:

```python
from huggingface_hub import snapshot_download
```

or the model library's `from_pretrained()` mechanism.

Hugging Face's Hub library supports downloading repositories and caching them locally. ([Hugging Face][3])

Example concept:

```python
model_path = snapshot_download(
    repo_id=MODEL_ID,
    token=os.getenv("HF_TOKEN")
)
```

The exact download mechanism must follow the selected Kokoro implementation.

---

# 19. Model Configuration

The model ID must **not be hardcoded throughout the application**.

Use:

```env
MODEL_ID=...
```

Example:

```env
MODEL_ID=hexgrad/Kokoro-82M
```

The developer must verify the exact model repository and required package before finalizing this value.

---

# 20. Hugging Face Cache

The service should support:

```env
HF_HOME=/app/.cache/huggingface
```

or:

```env
HF_HUB_CACHE=/app/.cache/huggingface/hub
```

Hugging Face documents these variables for controlling the local model/cache location. ([Hugging Face][1])

The purpose is to avoid unnecessarily downloading the model repeatedly.

---

# 21. Model Loading

The model should be loaded once rather than for every request.

### Bad

```text
Request
 ↓
Download model
 ↓
Load model
 ↓
Generate audio
```

### Correct

```text
Server startup
      ↓
Check model
      ↓
Download if necessary
      ↓
Load model
      ↓
Ready
      ↓
Request → Generate
Request → Generate
Request → Generate
```

---

# 22. Startup Behavior

At application startup:

1. Load configuration.
2. Validate required environment variables.
3. Initialize Hugging Face authentication.
4. Download model if not cached.
5. Load model.
6. Initialize TTS provider.
7. Mark service as ready.

If model loading fails, the application should fail clearly rather than pretending that the service is healthy.

---

# 23. Readiness Endpoint

In addition to:

```http
GET /health
```

the service should ideally provide:

```http
GET /ready
```

Example:

```json
{
  "status": "ready",
  "model_loaded": true
}
```

This is useful for deployment and monitoring.

---

# 24. Error Handling

The API must return structured errors.

Possible errors:

```text
UNAUTHORIZED
INVALID_REQUEST
TEXT_TOO_LONG
UNSUPPORTED_LANGUAGE
UNSUPPORTED_VOICE
UNSUPPORTED_FORMAT
MODEL_NOT_READY
TTS_GENERATION_FAILED
SERVER_BUSY
INTERNAL_ERROR
```

Example:

```json
{
  "error": "MODEL_NOT_READY",
  "message": "TTS model is still loading."
}
```

Never expose Python stack traces or secrets to clients.

---

# 25. Rate Limiting

The service should have basic protection against accidental abuse.

For example:

```text
Per API key:
X requests/minute
```

The exact limit should be configurable:

```env
RATE_LIMIT_PER_MINUTE=30
```

The implementation can start with simple in-memory rate limiting.

A distributed rate limiter is **not required for MVP**.

---

# 26. Request Size Limits

The server must protect itself against huge requests.

Example:

```env
MAX_TEXT_LENGTH=5000
```

The value must be configurable.

---

# 27. Logging

The service must log:

* Request timestamp
* Client/application ID
* Endpoint
* Request duration
* Success/failure
* Error category
* Generated audio duration if available

It must **not log**:

* API keys
* Hugging Face tokens
* Full user text by default

This is particularly important because book summaries could contain large amounts of user/content data.

---

# 28. Performance Requirements

The service must measure:

* Model loading time
* First-request latency
* Subsequent request latency
* Audio generation time
* CPU usage
* RAM usage
* Audio duration
* Real-time factor

Example:

```text
Input: 60 seconds of speech
Generation: 20 seconds

RTF = 20 / 60 = 0.33
```

The actual performance must be measured on the Render deployment environment rather than assumed.

---

# 29. Concurrency

The initial version should prioritize stability over maximum concurrency.

If the model cannot safely process multiple requests simultaneously, requests should be queued or limited.

The service must not crash because two applications send requests simultaneously.

---

# 30. Audio Storage

For MVP, the preferred approach is:

```text
Client
  ↓
TTS API
  ↓
Generate audio
  ↓
Return audio
  ↓
Client stores audio
```

The TTS service should **not become a permanent audio-storage service**.

If persistent storage is required later, use object storage such as S3-compatible storage.

Do not depend on Render's local filesystem for permanent audio.

---

# 31. API Documentation

FastAPI must expose:

```text
/docs
```

and:

```text
/openapi.json
```

The API documentation must contain:

* Authentication
* Request schema
* Response schema
* Error responses
* Example requests
* Example responses

---

# 32. API Endpoints

| Method | Endpoint     | Auth | Purpose             |
| ------ | ------------ | ---- | ------------------- |
| GET    | `/health`    | No   | Basic health        |
| GET    | `/ready`     | No   | Model readiness     |
| GET    | `/v1/info`   | Yes  | Service information |
| GET    | `/v1/voices` | Yes  | Available voices    |
| POST   | `/v1/speech` | Yes  | Generate speech     |

---

# 33. Example `/v1/speech`

### Request

```json
{
  "text": "The most important thing is to focus on one task at a time.",
  "language": "en",
  "voice": "default",
  "format": "mp3"
}
```

### Headers

```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Response

```http
200 OK
Content-Type: audio/mpeg
```

---

# 34. Configuration

The `.env.example` file should contain:

```env
# Application
APP_NAME=ai-tts-service
APP_ENV=production
PORT=8000

# Authentication
API_KEY_MINDPAGEREADS=
API_KEY_COURSIFY=

# Hugging Face
HF_TOKEN=

# Model
MODEL_ID=
MODEL_REVISION=

# TTS
DEFAULT_LANGUAGE=en
DEFAULT_VOICE=
DEFAULT_FORMAT=mp3
MAX_TEXT_LENGTH=5000

# Rate limiting
RATE_LIMIT_PER_MINUTE=30

# Hugging Face cache
HF_HOME=/app/.cache/huggingface
HF_HUB_CACHE=/app/.cache/huggingface/hub
```

**Do not commit `.env`.**

Commit only:

```text
.env.example
```

---

# 35. Docker Requirements

The project should provide a `Dockerfile`.

The Docker image must:

1. Install Python dependencies.
2. Install required system audio dependencies.
3. Copy application source.
4. Start FastAPI.
5. Respect the `PORT` environment variable.
6. Avoid storing secrets inside the image.

---

# 36. Render Deployment

The service must be deployable on Render.

Required Render configuration:

```text
Build:
pip install -r requirements.txt

Start:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

If Docker is used, Render should build and run the Docker image.

Environment variables must be configured through Render's environment/secrets configuration.

---

# 37. Testing Requirements

## Authentication

Test:

```text
Valid key       → 200
Invalid key     → 401
Missing key     → 401
```

## Validation

Test:

```text
Empty text      → 400
Huge text       → 400
Valid text      → 200
Invalid format  → 400
Invalid language→ 400
```

## TTS

Test:

```text
Short sentence
Paragraph
1-minute text
5-minute text
```

Verify:

* Audio exists.
* Audio is valid.
* Audio duration > 0.
* Audio can be decoded.
* Audio can be played.

---

# 38. Model Download Test

The deployment must be tested from a **clean environment**.

This is important.

We want to prove:

```text
Fresh Render instance
       ↓
HF_TOKEN
       ↓
Download model
       ↓
Load model
       ↓
Generate speech
```

The developer must document:

* Model repository
* Model version/revision
* Download size
* Cache location
* Download time
* Required RAM
* Required CPU/GPU

Hugging Face's CLI also supports downloading model repositories directly, including specifying a revision or local directory. ([Hugging Face][4])

---

# 39. Security Requirements

### NFR-01 — Secret Management

All secrets must be environment variables/secrets.

### NFR-02 — HTTPS

Production API must use HTTPS.

### NFR-03 — Authentication

All speech-generation endpoints must require authentication.

### NFR-04 — No Secret Logging

API keys and HF tokens must never appear in logs.

### NFR-05 — Input Protection

The service must enforce request and text-size limits.

### NFR-06 — Dependency Security

Dependencies must be pinned or constrained to tested versions.

---

# 40. Non-Functional Requirements

## NFR-07 — Reliability

The server should not crash because of an individual failed TTS request.

## NFR-08 — Performance

TTS generation should be benchmarked and documented.

## NFR-09 — Scalability

The architecture should permit multiple application clients and future providers.

## NFR-10 — Maintainability

Provider-specific implementation must remain isolated from API routes.

## NFR-11 — Portability

The service should run locally, through Docker, and on Render.

## NFR-12 — Observability

Logs must provide enough information to diagnose failures without exposing sensitive data.

## NFR-13 — Extensibility

New languages, voices, and TTS providers should be addable without breaking existing clients.

---

# 41. Recommended Repository Structure

```text
ai-tts-service/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── routes.py
│   │   └── schemas.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   └── kokoro.py
│   │
│   ├── services/
│   │   └── tts.py
│   │
│   └── config.py
│
├── tests/
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_validation.py
│   └── test_tts.py
│
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── render.yaml
├── README.md
└── LICENSE
```

---

# 42. Important Model Requirement

The developer **must not assume that the model will work simply because the Python package installs**.

They must perform an actual test:

```text
Text
 ↓
Tokenizer / frontend
 ↓
Kokoro
 ↓
Audio
 ↓
WAV/MP3
 ↓
Decode test
```

And confirm the generated audio is understandable English.

This matters because we already encountered environment/frontend issues during testing.

---

# 43. MVP Acceptance Criteria

The project is complete when all of the following are true:

* [ ] FastAPI service runs locally.
* [ ] FastAPI service runs in Docker.
* [ ] Service deploys successfully to Render.
* [ ] `/health` works.
* [ ] `/ready` works.
* [ ] API-key authentication works.
* [ ] Multiple client API keys are supported.
* [ ] Invalid keys are rejected.
* [ ] Text validation works.
* [ ] Kokoro model downloads successfully.
* [ ] Hugging Face authentication uses `HF_TOKEN`.
* [ ] Model is cached.
* [ ] Model loads successfully.
* [ ] English speech is generated.
* [ ] MP3/WAV output works.
* [ ] `/v1/voices` works.
* [ ] `/v1/info` works.
* [ ] Swagger documentation works.
* [ ] Automated tests exist.
* [ ] No secrets are committed.
* [ ] Performance is benchmarked.
* [ ] RAM requirements are documented.
* [ ] Render deployment instructions are documented.
* [ ] Another application can consume the API successfully.

---

# 44. Future Roadmap

These are **not MVP requirements**.

### Phase 2

```text
Hindi
Hinglish
More voices
Better audio formats
Usage analytics
```

### Phase 3

```text
Multiple TTS providers
Provider fallback
Usage quotas
Client dashboard
API key management
Persistent audio storage
Background jobs
```

### Phase 4

```text
Streaming TTS
Long-form generation
Voice customization
Automatic provider selection
Cost-based provider routing
```

---

# 45. Final Principle

The most important architectural rule is:

> **Clients should know that they are talking to a TTS API, not which TTS model is running behind it.**

Today:

```text
MindpageReads
      ↓
AI TTS Service
      ↓
Kokoro
```

Tomorrow:

```text
MindpageReads
      ↓
AI TTS Service
      ↓
Best available provider
```

The MindpageReads code should **not need to change** just because we replace Kokoro.

That's what makes this useful across **MindpageReads, Coursify, OnlyFounders, and future projects** rather than building a one-off service.




That should keep the scope **very clear** and prevent the classic “I built a whole platform instead of the tiny service you asked for” situation. 😄

[1]: https://huggingface.co/docs/huggingface_hub/main/package_reference/environment_variables?utm_source=chatgpt.com "Environment variables · Hugging Face"
[2]: https://huggingface.co/IrieDinamik/kokoro?utm_source=chatgpt.com "IrieDinamik/kokoro · Hugging Face"
[3]: https://huggingface.co/docs/huggingface_hub/package_reference/file_download?utm_source=chatgpt.com "Downloading files · Hugging Face"
[4]: https://huggingface.co/docs/huggingface_hub/main/package_reference/cli?utm_source=chatgpt.com "hf · Hugging Face"

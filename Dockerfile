# CPU-only PyTorch. The default PyPI Linux wheel bundles ~2GB of CUDA
# libraries that Render's CPU instances can never use (SRS 12, NFR-08).
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    PORT=8000

# libgomp1: OpenMP runtime required by torch and libsndfile (MP3 encoding).
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel \
    && pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt ./
RUN pip install -r requirements.txt

# spaCy model used by the English G2P front-end. Installed at build time so the
# first request never waits on a download (misaki does this lazily otherwise).
RUN pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"

# Bake the Kokoro weights into the image so cold starts do not re-download them.
# The pinned revision keeps the image reproducible. The model is public, so no
# token is used here; for a gated repo build with PREDOWNLOAD_MODEL=false and
# set HF_TOKEN as a runtime secret instead (never as a build arg).
ARG MODEL_ID=hexgrad/Kokoro-82M
ARG MODEL_REVISION=f3ff3571791e39611d31c381e3a41a3af07b4987
ARG PREDOWNLOAD_MODEL=true
RUN if [ "$PREDOWNLOAD_MODEL" = "true" ]; then \
      python -c "from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='${MODEL_ID}', revision='${MODEL_REVISION}', \
allow_patterns=['config.json','kokoro-v1_0.pth','voices/*.pt'])" ; \
    fi

COPY app ./app
COPY scripts ./scripts

# Run as a non-root user (SRS 35).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/ready" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

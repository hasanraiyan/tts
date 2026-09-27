# Memory-light image: Kokoro v1.0 on ONNX Runtime via sherpa-onnx.
#
# PyTorch is deliberately absent. It would add ~1GB to the image and ~1.3GB of
# RAM at inference time, which does not fit Render's 512MB plans. Build the
# PyTorch variant with:  docker build --build-arg TTS_RUNTIME=torch .
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TTS_PROVIDER=onnx \
    ONNX_MODEL_DIR=/app/models/kokoro-int8-multi-lang-v1_0 \
    HF_HOME=/app/.cache/huggingface \
    PORT=8000

# libgomp1: OpenMP runtime used by onnxruntime and libsndfile (MP3 encoding).
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Optional PyTorch runtime. Off by default: see requirements-torch.txt.
ARG TTS_RUNTIME=onnx
RUN if [ "$TTS_RUNTIME" = "torch" ]; then \
      pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu && \
      pip install -r requirements-torch.txt && \
      pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl" ; \
    fi

# Bake the int8 Kokoro v1.0 model into the image so a cold start never waits on
# a 126MB download. Same Apache-2.0 weights as the PyTorch path, quantised.
# Downloaded from the sherpa-onnx tts-models release; no token required.
ARG ONNX_MODEL_URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_0.tar.bz2
ARG PREDOWNLOAD_ONNX_MODEL=true
RUN if [ "$PREDOWNLOAD_ONNX_MODEL" = "true" ]; then \
      mkdir -p /app/models && \
      curl -fsSL "$ONNX_MODEL_URL" -o /tmp/model.tar.bz2 && \
      tar -xjf /tmp/model.tar.bz2 -C /app/models && \
      rm /tmp/model.tar.bz2 && \
      test -f "${ONNX_MODEL_DIR}/model.int8.onnx" ; \
    fi

COPY app ./app
COPY scripts ./scripts
# Apache-2.0 section 4 requires shipping the licence and attribution notices
# alongside the redistributed Kokoro weights baked in above.
COPY THIRD_PARTY_NOTICES.md ./THIRD_PARTY_NOTICES.md
COPY licenses ./licenses

# Run as a non-root user (SRS 35).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# /ready is 503 until the model is loaded, so a container that cannot generate
# speech is reported unhealthy instead of silently serving broken audio.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/ready" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

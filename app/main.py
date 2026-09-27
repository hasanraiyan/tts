"""Application factory and startup behaviour (SRS 22, 23, 24, 27, 31)."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings, get_settings
from app.errors import APIError, ErrorCode
from app.logging_config import configure_logging, get_logger
from app.state import get_runtime

logger = get_logger(__name__)

DESCRIPTION = """
Generic text-to-speech API.

* `POST /v1/speech` turns text into speech (mp3 or wav).
* `GET /v1/voices` lists the voices available right now.
* `GET /v1/info` reports the active provider, model revision and limits.

Authenticate every `/v1/*` call with `Authorization: Bearer <API_KEY>`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    runtime = get_runtime()

    if settings.preload_model:
        started = time.perf_counter()
        try:
            runtime.load()
            logger.info("startup complete in %.1fs", time.perf_counter() - started)
        except Exception:  # noqa: BLE001
            # /health stays 200 (process is alive) while /ready reports the
            # failure, so a broken model never masquerades as healthy.
            logger.exception("model failed to load; service will report not_ready")
    else:
        logger.info("preload_model disabled; model will load on first request")

    runtime.jobs.start()

    yield

    runtime.jobs.stop()
    logger.info("shutting down")


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        headers = {}
        if exc.code == ErrorCode.RATE_LIMITED and "retry_after_seconds" in exc.extra:
            headers["Retry-After"] = str(exc.extra["retry_after_seconds"])
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload(), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "body"
        return JSONResponse(
            status_code=400,
            content={
                "error": ErrorCode.INVALID_REQUEST,
                "message": f"Invalid request field '{field}': {first.get('msg', 'validation failed')}",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": ErrorCode.INTERNAL_ERROR,
                "message": "Internal server error.",
            },
        )


def _register_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        client_id = getattr(request.state, "client_id", None)
        audio_seconds = getattr(request.state, "audio_seconds", None)
        generation_seconds = getattr(request.state, "generation_seconds", None)
        characters = getattr(request.state, "characters", None)

        logger.info(
            "request method=%s path=%s client=%s status=%s duration_ms=%.1f chars=%s audio_s=%s gen_s=%s",
            request.method,
            request.url.path,
            client_id or "anonymous",
            response.status_code,
            duration_ms,
            characters,
            f"{audio_seconds:.2f}" if audio_seconds is not None else None,
            f"{generation_seconds:.2f}" if generation_seconds is not None else None,
        )
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="AI TTS Service",
        version=settings.app_version,
        description=DESCRIPTION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(router)
    _register_error_handlers(app)
    _register_logging_middleware(app)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()

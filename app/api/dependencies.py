"""Shared FastAPI dependencies: settings, API-key auth, rate limiting."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import APIError, ErrorCode, unauthorized
from app.services.rate_limit import RateLimiter


@dataclass(frozen=True)
class ClientContext:
    """Identifies the calling application (SRS 9). Never contains the key."""

    client_id: str


def settings_dependency() -> Settings:
    return get_settings()


def verify_api_key(
    request: Request,
    settings: Settings = Depends(settings_dependency),
) -> ClientContext:
    """Bearer-token auth against API_KEY_<CLIENT_ID> env vars (SRS 8/9/10)."""
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized("Missing or malformed Authorization header. Expected: Bearer <API_KEY>.")

    presented = token.strip()
    configured = settings.api_keys
    if not configured:
        raise APIError(
            ErrorCode.INTERNAL_ERROR,
            "Service is not configured with any API keys.",
            status_code=500,
        )

    # Constant-time compare across every key: no timing signal, and it still
    # tells us which client authenticated.
    matched: str | None = None
    for client_id, expected in configured.items():
        if hmac.compare_digest(presented, expected):
            matched = client_id
    if matched is None:
        raise unauthorized()

    request.state.client_id = matched
    return ClientContext(client_id=matched)


def rate_limit_dependency(
    client: ClientContext = Depends(verify_api_key),
    settings: Settings = Depends(settings_dependency),
) -> None:
    limiter: RateLimiter = request_limiter(settings)
    limiter.check(client.client_id)


_limiter: RateLimiter | None = None


def request_limiter(settings: Settings) -> RateLimiter:
    global _limiter
    if _limiter is None or _limiter.limit != settings.rate_limit_per_minute:
        _limiter = RateLimiter(settings.rate_limit_per_minute)
    return _limiter

"""In-memory per-client rate limiting (SRS 25)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.errors import APIError, ErrorCode


class RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._limit = max(0, requests_per_minute)
        self._window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @property
    def limit(self) -> int:
        return self._limit

    def check(self, client_id: str) -> None:
        if self._limit == 0:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client_id]
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                retry_after = max(1, int(self._window - (now - hits[0])))
                raise APIError(
                    ErrorCode.RATE_LIMITED,
                    "Rate limit exceeded. Retry later.",
                    status_code=429,
                    retry_after_seconds=retry_after,
                )
            hits.append(now)

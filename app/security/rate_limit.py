"""Лимит запросов: RATE_LIMIT_PER_MIN на ключ."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.config import get_settings
from app.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                raise AppError(
                    "RATE_LIMITED",
                    "Превышен лимит запросов. Попробуйте позже.",
                    status_code=429,
                )
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


async def enforce_rate_limit(request: Request) -> None:
    settings = get_settings()
    api_key = getattr(request.state, "api_key", None) or "anonymous"
    rate_limiter.check(api_key, settings.rate_limit_per_min)

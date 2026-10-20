"""Кэш результатов в памяти (TTL + max items)."""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache
from threading import Lock

from app.config import get_settings


class ParseCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cache: TTLCache[str, dict[str, Any]] | None = None

    def _ensure(self) -> TTLCache[str, dict[str, Any]]:
        settings = get_settings()
        if self._cache is None:
            self._cache = TTLCache(
                maxsize=settings.cache_max_items,
                ttl=settings.cache_ttl_s,
            )
        return self._cache

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._ensure().get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._ensure()[key] = value

    def clear(self) -> None:
        with self._lock:
            if self._cache is not None:
                self._cache.clear()
            self._cache = None


parse_cache = ParseCache()

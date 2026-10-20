"""Проверка X-API-Key (сравнение защищено от подбора по времени)."""

from __future__ import annotations

import hmac

from fastapi import Header, Request

from app.config import get_settings
from app.errors import AppError

_HMAC_KEY = b"parser-service-api-key-cmp"


def _key_matches(provided: str, allowed: frozenset[str]) -> bool:
    """Сравнивает ключ со всеми разрешёнными через hmac.compare_digest (без утечки по времени)."""
    provided_digest = hmac.new(_HMAC_KEY, provided.encode("utf-8"), "sha256").digest()
    matched = False
    for key in allowed:
        candidate = hmac.new(_HMAC_KEY, key.encode("utf-8"), "sha256").digest()
        # Не делаем early-return: проходим все ключи
        if hmac.compare_digest(provided_digest, candidate):
            matched = True
    return matched


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    settings = get_settings()
    if not x_api_key or not _key_matches(x_api_key, settings.api_keys):
        raise AppError(
            "UNAUTHORIZED",
            "Требуется действительный заголовок X-API-Key",
            status_code=401,
        )
    request.state.api_key = x_api_key
    return x_api_key

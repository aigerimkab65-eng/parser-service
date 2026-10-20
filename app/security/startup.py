"""Проверки конфигурации при старте (слабые ключи, опасные флаги)."""

from __future__ import annotations

import logging
import re
import sys

from app.config import Settings

logger = logging.getLogger("parser-service.security")

_WEAK_KEYS = frozenset(
    {
        "dev-key-change-me",
        "changeme",
        "change-me",
        "secret",
        "password",
        "test",
        "test-key",
        "api-key",
        "123456",
    }
)

_WEAK_RE = re.compile(r"^(test|dev|demo|default).{0,12}$", re.I)

# В production ключ должен быть длинным (openssl rand -hex 32 → 64 символа; минимум 32)
_MIN_PROD_KEY_LEN = 32


def api_keys_look_weak(keys: frozenset[str]) -> list[str]:
    weak: list[str] = []
    for key in keys:
        if len(key) < 16 or key.lower() in _WEAK_KEYS or _WEAK_RE.match(key):
            weak.append(key)
    return weak


def _production_key_problems(keys: frozenset[str]) -> list[str]:
    problems: list[str] = []
    if not keys:
        problems.append("API_KEYS пуст — задайте длинный секретный ключ")
        return problems
    for key in keys:
        if key == "dev-key-change-me":
            problems.append(
                "API_KEYS=dev-key-change-me запрещён в рабочем режиме "
                "(это учебный ключ). Сгенерируйте: openssl rand -hex 32"
            )
        elif len(key) < _MIN_PROD_KEY_LEN:
            problems.append(
                f"API_KEYS слишком короткий ({len(key)} символов, нужно ≥ {_MIN_PROD_KEY_LEN}). "
                "Сгенерируйте: openssl rand -hex 32"
            )
    return problems


def enforce_startup_or_exit(settings: Settings) -> None:
    """В production слабый/пустой ключ — сервис не стартует. APP_ENV=dev — только предупреждения."""
    is_dev = settings.app_env == "dev"
    problems = _production_key_problems(settings.api_keys)

    if problems and not is_dev:
        for msg in problems:
            logger.error("%s", msg)
        logger.error(
            "Запуск остановлен. Для локальной проверки на Mac поставьте APP_ENV=dev "
            "и ключ в .env. Для VPS — сильный API_KEYS (≥32 символов)."
        )
        raise SystemExit(1)

    if problems and is_dev:
        for msg in problems:
            logger.warning("[APP_ENV=dev] %s", msg)


def log_security_warnings(settings: Settings) -> None:
    enforce_startup_or_exit(settings)

    weak = api_keys_look_weak(settings.api_keys)
    if weak and settings.app_env == "dev":
        logger.warning(
            "Слабые API_KEYS (%s шт.) допустимы только при APP_ENV=dev.",
            len(weak),
        )

    if settings.browser_enabled:
        logger.warning(
            "BROWSER_ENABLED=true: DNS rebinding в браузере закрыт не полностью. "
            "На VPS рекомендуется false, если браузер не нужен."
        )

    if settings.docs_enabled:
        logger.warning("DOCS_ENABLED=true — OpenAPI/docs доступны публично")

    if settings.ui_enabled:
        logger.warning(
            "UI_ENABLED=true — панель / и POST /ui/parse без API-ключа. "
            "На публичном VPS лучше false."
        )
    else:
        logger.info("UI_ENABLED=false — тестовая панель отключена")

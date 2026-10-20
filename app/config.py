"""Настройки сервиса из переменных окружения (раздел 7 ТЗ)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _split_csv(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    val = raw.strip().lower()
    if val in {"1", "true", "yes", "on", "full"}:
        return True
    if val in {"0", "false", "no", "off", "lite"}:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    api_keys: frozenset[str] = field(default_factory=frozenset)
    app_env: str = "production"
    fetch_timeout_s: float = 15.0
    max_page_bytes: int = 5 * 1024 * 1024  # MAX_PAGE_MB=5
    max_redirects: int = 5
    min_text_chars: int = 200
    cache_ttl_s: int = 3600
    cache_max_items: int = 500
    rate_limit_per_min: int = 60
    browser_enabled: bool = False
    browser_timeout_s: float = 20.0
    browser_max_pages: int = 2
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
    docs_enabled: bool = False
    ui_enabled: bool = True
    respect_robots: bool = True
    log_level: str = "INFO"
    allowed_ports: frozenset[int] = field(default_factory=lambda: frozenset({80, 443}))
    variant: str = "lite"
    app_version: str = "1.0.0"
    git_commit: str = "unknown"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_env = (os.getenv("APP_ENV") or "production").strip().lower()
    keys_raw = os.getenv("API_KEYS") or os.getenv("PARSER_API_KEYS") or ""
    # В режиме разработки разрешаем привычный локальный ключ, если не задан
    if not keys_raw.strip() and app_env == "dev":
        keys_raw = "dev-key-change-me"
    max_page_mb = _env_float("MAX_PAGE_MB", 5.0)
    variant = (os.getenv("PARSER_VARIANT") or "lite").strip().lower()
    browser_default = variant == "full"
    return Settings(
        api_keys=_split_csv(keys_raw),
        app_env=app_env,
        fetch_timeout_s=_env_float("FETCH_TIMEOUT_S", 15.0),
        max_page_bytes=int(max_page_mb * 1024 * 1024),
        max_redirects=_env_int("MAX_REDIRECTS", 5),
        min_text_chars=_env_int("MIN_TEXT_CHARS", 200),
        cache_ttl_s=_env_int("CACHE_TTL_S", 3600),
        cache_max_items=_env_int("CACHE_MAX_ITEMS", 500),
        rate_limit_per_min=_env_int("RATE_LIMIT_PER_MIN", 60),
        browser_enabled=_env_bool("BROWSER_ENABLED", browser_default),
        browser_timeout_s=_env_float("BROWSER_TIMEOUT_S", 20.0),
        browser_max_pages=_env_int("BROWSER_MAX_PAGES", 2),
        user_agent=os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36",
        ),
        docs_enabled=_env_bool("DOCS_ENABLED", False),
        ui_enabled=_env_bool("UI_ENABLED", True),
        respect_robots=_env_bool("RESPECT_ROBOTS", True),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        allowed_ports=_split_ports(os.getenv("ALLOWED_PORTS", "80,443")),
        variant=variant,
        app_version=(os.getenv("APP_VERSION") or "1.0.0").strip(),
        git_commit=(os.getenv("GIT_COMMIT") or "unknown").strip(),
    )


def _split_ports(value: str) -> frozenset[int]:
    ports: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            ports.add(int(item))
    return frozenset(ports) or frozenset({80, 443})


def reset_settings_cache() -> None:
    get_settings.cache_clear()

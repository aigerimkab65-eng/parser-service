"""Общие фикстуры pytest."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["APP_ENV"] = "dev"
os.environ["API_KEYS"] = "test-key"
os.environ["RATE_LIMIT_PER_MIN"] = "1000"
os.environ["CACHE_TTL_S"] = "60"
os.environ["CACHE_MAX_ITEMS"] = "32"
os.environ["BROWSER_ENABLED"] = "false"
os.environ["MIN_TEXT_CHARS"] = "200"
os.environ["DOCS_ENABLED"] = "false"
os.environ["RESPECT_ROBOTS"] = "false"  # в юнит-тестах не ходим за robots.txt
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("GIT_COMMIT", "test")
os.environ.setdefault("PARSER_VARIANT", "lite")

from app.config import reset_settings_cache
from app.main import app
from app.security.rate_limit import rate_limiter
from app.services.cache import parse_cache
from tests.asgi_client import ASGIClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clean_state():
    reset_settings_cache()
    parse_cache.clear()
    rate_limiter.reset()
    yield
    parse_cache.clear()
    rate_limiter.reset()
    reset_settings_cache()


@pytest.fixture
def client() -> ASGIClient:
    return ASGIClient(app)


@pytest.fixture
def api_headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES

"""Проверки enforce_startup_or_exit и GET /version."""

from __future__ import annotations

import os

import pytest

from app.config import Settings, reset_settings_cache
from app.security.startup import enforce_startup_or_exit


def test_production_rejects_dev_key():
    settings = Settings(
        api_keys=frozenset({"dev-key-change-me"}),
        app_env="production",
    )
    with pytest.raises(SystemExit) as exc:
        enforce_startup_or_exit(settings)
    assert exc.value.code == 1


def test_production_rejects_short_key():
    settings = Settings(
        api_keys=frozenset({"short-but-not-dev"}),
        app_env="production",
    )
    with pytest.raises(SystemExit):
        enforce_startup_or_exit(settings)


def test_production_accepts_long_key():
    settings = Settings(
        api_keys=frozenset({"a" * 32}),
        app_env="production",
    )
    enforce_startup_or_exit(settings)  # no raise


def test_dev_allows_weak_key():
    settings = Settings(
        api_keys=frozenset({"dev-key-change-me"}),
        app_env="dev",
    )
    enforce_startup_or_exit(settings)  # warnings only


def test_version_endpoint(client):
    os.environ["APP_VERSION"] = "1.0.0"
    os.environ["GIT_COMMIT"] = "abc1234"
    os.environ["PARSER_VARIANT"] = "lite"
    reset_settings_cache()
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"
    assert data["commit"] == "abc1234"
    assert data["variant"] == "lite"

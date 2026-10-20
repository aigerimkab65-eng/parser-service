"""Заголовки безопасности и проверка слабых ключей."""

from __future__ import annotations

from app.security.headers import SECURITY_HEADERS
from app.security.startup import api_keys_look_weak
from tests.asgi_client import ASGIClient


def test_security_headers_on_health(client: ASGIClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "no-referrer"
    csp = headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_api_no_store_cache(client: ASGIClient, api_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/parse",
        headers=api_headers,
        json={"url": "http://127.0.0.1/", "use_cache": False},
    )
    assert response.status_code == 403
    assert "no-store" in response.headers.get("cache-control", "")


def test_weak_api_keys_detected() -> None:
    assert api_keys_look_weak(frozenset({"dev-key-change-me"}))
    assert api_keys_look_weak(frozenset({"short"}))
    assert not api_keys_look_weak(frozenset({"a" * 32 + "-strong-enough-key"}))


def test_security_headers_constant_complete() -> None:
    for name in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
        "Permissions-Policy",
    ):
        assert name in SECURITY_HEADERS

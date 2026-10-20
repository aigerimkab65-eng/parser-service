"""Тесты HTTP API: ключ, формат ответа, кэш, лимиты."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.config import reset_settings_cache
from app.security.rate_limit import rate_limiter
from app.services.fetch import FetchedPage
from tests.asgi_client import ASGIClient

RESPONSE_FIELDS = {
    "url",
    "final_url",
    "title",
    "description",
    "author",
    "published_date",
    "site_name",
    "language",
    "main_image",
    "images",
    "links",
    "content_markdown",
    "content_text",
    "word_count",
    "render_used",
    "from_cache",
    "fetched_at",
    "duration_ms",
}


def test_health(client: ASGIClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "browser_enabled" in body


def test_unauthorized(client: ASGIClient) -> None:
    response = client.post("/v1/parse", json={"url": "https://example.com/"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_ui_parse_without_api_key(client: ASGIClient) -> None:
    """UI не требует X-API-Key: доходит до проверки URL (не 401)."""
    response = client.post("/ui/parse", json={"url": "http://127.0.0.1/"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_HOST"


def test_ui_rejects_cross_site(client: ASGIClient) -> None:
    response = client.post(
        "/ui/parse",
        headers={"Sec-Fetch-Site": "cross-site"},
        json={"url": "http://127.0.0.1/"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_ui_rejects_foreign_origin(client: ASGIClient) -> None:
    response = client.post(
        "/ui/parse",
        headers={"Origin": "https://evil.example", "Host": "parser.example"},
        json={"url": "http://127.0.0.1/"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_ui_static_by_default(
    client: ASGIClient,
    fixtures_dir: Path,
) -> None:
    """Без use_browser — только static; картинки по флагу include_images."""
    html = (fixtures_dir / "news_article.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/news",
        final_url="https://example.com/news",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    with (
        patch("app.services.pipeline.validate_url_for_fetch", return_value="https://example.com/news"),
        patch("app.services.pipeline.is_allowed_by_robots", new=AsyncMock(return_value=True)),
        patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=page)) as fetch_mock,
        patch("app.services.pipeline.fetch_page_with_browser", new=AsyncMock()) as browser_mock,
    ):
        response = client.post(
            "/ui/parse",
            json={
                "url": "https://example.com/news",
                "include_images": True,
                "use_cache": False,
                "use_browser": False,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["render_used"] == "static"
    assert fetch_mock.await_count == 1
    assert browser_mock.await_count == 0
    assert isinstance(body.get("images"), list)


def test_ui_browser_falls_back_to_static(
    client: ASGIClient,
    fixtures_dir: Path,
) -> None:
    """use_browser при выключенном браузере → тихо static, без ошибки."""
    html = (fixtures_dir / "news_article.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/news",
        final_url="https://example.com/news",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    with (
        patch("app.routes.ui.playwright_available", return_value=False),
        patch("app.services.pipeline.validate_url_for_fetch", return_value="https://example.com/news"),
        patch("app.services.pipeline.is_allowed_by_robots", new=AsyncMock(return_value=True)),
        patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=page)),
        patch("app.services.pipeline.fetch_page_with_browser", new=AsyncMock()) as browser_mock,
    ):
        response = client.post(
            "/ui/parse",
            json={"url": "https://example.com/news", "use_browser": True, "use_cache": False},
        )
    assert response.status_code == 200
    assert response.json()["render_used"] == "static"
    assert browser_mock.await_count == 0


def test_ui_html_is_beginner_simple() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="apiKey"' not in html
    assert "apiKey" not in html
    assert "includeImages" not in html
    assert "useBrowser" not in html
    assert "Проверка страницы" in html
    assert "/ui/parse" in js


def test_invalid_url(client: ASGIClient, api_headers: dict[str, str]) -> None:
    response = client.post("/v1/parse", headers=api_headers, json={"url": "not-a-url"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_URL"


def test_forbidden_host_via_api(client: ASGIClient, api_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/parse",
        headers=api_headers,
        json={"url": "http://127.0.0.1/"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_HOST"


def test_parse_success_shape(
    client: ASGIClient,
    api_headers: dict[str, str],
    fixtures_dir: Path,
) -> None:
    html = (fixtures_dir / "news_article.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/news",
        final_url="https://example.com/news",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    with patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=page)):
        response = client.post(
            "/v1/parse",
            headers=api_headers,
            json={"url": "https://example.com/news", "render": "never"},
        )
    assert response.status_code == 200
    body = response.json()
    assert RESPONSE_FIELDS.issubset(body.keys())
    assert body["from_cache"] is False
    assert body["render_used"] == "static"
    assert body["content_text"]
    assert body["word_count"] > 0


def test_cache_hit(
    client: ASGIClient,
    api_headers: dict[str, str],
    fixtures_dir: Path,
) -> None:
    html = (fixtures_dir / "blog_ru.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/blog",
        final_url="https://example.com/blog",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    mock_fetch = AsyncMock(return_value=page)
    payload = {"url": "https://example.com/blog", "render": "never", "use_cache": True}
    with patch("app.services.pipeline.fetch_page", new=mock_fetch):
        first = client.post("/v1/parse", headers=api_headers, json=payload)
        second = client.post("/v1/parse", headers=api_headers, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is True
    assert mock_fetch.await_count == 1


def test_rate_limit(client: ASGIClient, api_headers: dict[str, str], fixtures_dir: Path) -> None:
    os.environ["RATE_LIMIT_PER_MIN"] = "2"
    reset_settings_cache()
    rate_limiter.reset()
    html = (fixtures_dir / "landing.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/x",
        final_url="https://example.com/x",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    try:
        with patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=page)):
            assert client.post("/v1/parse", headers=api_headers, json={"url": "https://example.com/a1", "render": "never"}).status_code == 200
            assert client.post("/v1/parse", headers=api_headers, json={"url": "https://example.com/a2", "render": "never"}).status_code == 200
            limited = client.post("/v1/parse", headers=api_headers, json={"url": "https://example.com/a3", "render": "never"})
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
    finally:
        os.environ["RATE_LIMIT_PER_MIN"] = "1000"
        reset_settings_cache()
        rate_limiter.reset()


def test_stage1_always_acts_as_never(
    client: ASGIClient,
    api_headers: dict[str, str],
    fixtures_dir: Path,
) -> None:
    """Пока браузер выключен, always работает как never, render_used=static."""
    html = (fixtures_dir / "product.html").read_text(encoding="utf-8")
    page = FetchedPage(
        url="https://example.com/product",
        final_url="https://example.com/product",
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    with patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=page)):
        response = client.post(
            "/v1/parse",
            headers=api_headers,
            json={"url": "https://example.com/product", "render": "always"},
        )
    assert response.status_code == 200
    assert response.json()["render_used"] == "static"

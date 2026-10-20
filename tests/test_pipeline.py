"""Тесты auto → browser и batch."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import anyio
from pydantic import HttpUrl

from app.config import reset_settings_cache
from app.routes.parse import parse_batch
from app.schemas import ParseBatchRequest, ParseRequest
from app.services.fetch import FetchedPage
from app.services.pipeline import parse_one


def _page(html: str, url: str = "https://example.com/a") -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )


def test_auto_stays_static_when_enough_text(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "news_article.html").read_text(encoding="utf-8")
    browser = AsyncMock()

    async def run() -> None:
        os.environ["BROWSER_ENABLED"] = "true"
        reset_settings_cache()
        try:
            with (
                patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=_page(html))),
                patch("app.services.pipeline.fetch_page_with_browser", new=browser),
                patch("app.services.pipeline.playwright_available", return_value=True),
            ):
                result = await parse_one(
                    ParseRequest(url="https://example.com/a", render="auto", use_cache=False)
                )
            assert result.render_used == "static"
            browser.assert_not_awaited()
        finally:
            os.environ["BROWSER_ENABLED"] = "false"
            reset_settings_cache()

    anyio.run(run)


def test_auto_falls_back_to_browser() -> None:
    thin = _page("<html><body><p>ok</p></body></html>", "https://example.com/thin")
    rich = _page(
        """
        <html><head><title>JS Page</title></head><body><article>
        <h1>JS Page</h1>
        <p>После рендера JavaScript появился полноценный текст статьи. Здесь достаточно
        символов, чтобы пройти порог MIN_TEXT_CHARS и подтвердить работу браузера.</p>
        <p>Второй абзац нужен для объёма и проверки извлечения Markdown.</p>
        </article></body></html>
        """,
        "https://example.com/thin",
    )

    async def run() -> None:
        os.environ["BROWSER_ENABLED"] = "true"
        os.environ["MIN_TEXT_CHARS"] = "200"
        reset_settings_cache()
        try:
            with (
                patch("app.services.pipeline.fetch_page", new=AsyncMock(return_value=thin)),
                patch(
                    "app.services.pipeline.fetch_page_with_browser",
                    new=AsyncMock(return_value=rich),
                ),
                patch("app.services.pipeline.playwright_available", return_value=True),
            ):
                result = await parse_one(
                    ParseRequest(url="https://example.com/thin", render="auto", use_cache=False)
                )
            assert result.render_used == "browser"
            assert result.content_text and len(result.content_text) > 50
        finally:
            os.environ["BROWSER_ENABLED"] = "false"
            reset_settings_cache()

    anyio.run(run)


def test_batch_mixed(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "landing.html").read_text(encoding="utf-8")

    async def run() -> None:
        with patch(
            "app.services.pipeline.fetch_page",
            new=AsyncMock(return_value=_page(html, "https://example.com/1")),
        ):
            body = ParseBatchRequest(
                urls=[HttpUrl("https://example.com/1"), HttpUrl("http://127.0.0.1/")],
                render="never",
                use_cache=False,
            )
            result = await parse_batch(body)
        assert len(result.results) == 2
        assert result.results[0].ok is True
        assert result.results[1].ok is False
        assert result.results[1].error is not None
        assert result.results[1].error["code"] == "FORBIDDEN_HOST"

    anyio.run(run)

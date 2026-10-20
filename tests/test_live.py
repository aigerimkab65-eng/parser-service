"""Живые тесты на реальных ссылках — запускать вручную: pytest -m live."""

from __future__ import annotations

import os

import anyio
import pytest

from app.config import reset_settings_cache
from app.schemas import ParseRequest
from app.services.pipeline import parse_one

pytestmark = pytest.mark.live

LIVE_URLS = [
    "https://example.com/",
    "https://www.wikipedia.org/",
    "https://docs.python.org/3/",
    "https://httpbin.org/html",
    "https://habr.com/ru/articles/",
]

# Конкретная статья (не лента): длина текста — страховка от обрезки gzip
HABR_ARTICLE = "https://habr.com/ru/articles/1089544/"


@pytest.fixture(autouse=True)
def _keys():
    os.environ.setdefault("API_KEYS", "test-key")
    reset_settings_cache()
    yield


@pytest.mark.parametrize("url", LIVE_URLS)
def test_live_parse(url: str) -> None:
    async def run() -> None:
        result = await parse_one(ParseRequest(url=url, render="never", use_cache=False))
        assert result.content_text or result.title
        assert result.render_used == "static"

    anyio.run(run)


def test_live_habr_article_text_not_truncated() -> None:
    """Статья Хабра: content_text > 3000 символов (обрезка gzip больше не пройдёт)."""

    async def run() -> None:
        result = await parse_one(
            ParseRequest(url=HABR_ARTICLE, render="never", use_cache=False)
        )
        assert result.render_used == "static"
        text = result.content_text or ""
        assert len(text) > 3000, f"ожидали >3000 символов, получили {len(text)}"

    anyio.run(run)

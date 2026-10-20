"""Извлечение на сохранённых HTML (без интернета)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.fetch import _decode_body
from app.services.parse import parse_html_string

REQUIRED_FIELDS = {
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


@pytest.mark.parametrize(
    "filename",
    [
        "news_article.html",
        "blog_ru.html",
        "landing.html",
        "product.html",
    ],
)
def test_extract_fixtures(fixtures_dir: Path, filename: str) -> None:
    html = (fixtures_dir / filename).read_text(encoding="utf-8")
    result = parse_html_string(html, url=f"https://example.com/{filename}")
    data = result.model_dump()
    assert REQUIRED_FIELDS.issubset(data.keys())
    assert result.content_text
    assert len(result.content_text) >= 100
    assert result.content_markdown
    assert result.title
    # без явного мусора меню
    assert "Баннер рекламы" not in (result.content_text or "")


def test_windows1251(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "article_cp1251.html").read_bytes()
    html, encoding = _decode_body(raw, "text/html; charset=windows-1251")
    assert encoding and ("1251" in encoding or encoding.lower() in {"cp1251", "windows-1251"})
    assert "кириллица" in html.lower() or "привет" in html.lower()
    result = parse_html_string(html, url="https://example.com/cp1251")
    assert result.content_text
    assert "привет" in result.content_text.lower() or "кириллица" in result.content_text.lower()


def test_og_fallback() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="Только OG">
      <meta property="og:description" content="OG описание">
      <meta property="og:image" content="https://example.com/i.jpg">
    </head><body><p>Достаточно длинный текст статьи для извлечения основного содержимого
    без лишних деталей меню. Повторяем мысль ещё раз, чтобы набрать символы.</p></body></html>
    """
    result = parse_html_string(html)
    assert result.title == "Только OG" or result.description == "OG описание"
    assert result.main_image == "https://example.com/i.jpg" or result.description

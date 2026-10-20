"""Извлечение текста и метаданных через trafilatura + og:-теги."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin

import trafilatura
from trafilatura.metadata import extract_metadata

from app.schemas import LinkItem, ParseResponse
from app.services.fetch import FetchedPage

_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](og:[^"\']+|twitter:[^"\']+|description|author)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_OG_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\'](og:[^"\']+|twitter:[^"\']+|description|author)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_A_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = unescape(re.sub(r"\s+", " ", value)).strip()
    return text or None


def _extract_og_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for match in _OG_RE.finditer(html):
        tags.setdefault(match.group(1).lower(), match.group(2))
    for match in _OG_RE_ALT.finditer(html):
        tags.setdefault(match.group(2).lower(), match.group(1))
    title_match = _TITLE_RE.search(html)
    if title_match:
        tags.setdefault("title", title_match.group(1))
    return tags


def _meta_from_trafilatura(html: str, url: str) -> dict[str, Any]:
    try:
        meta = extract_metadata(html, default_url=url)
    except Exception:
        return {}
    if meta is None:
        return {}
    if hasattr(meta, "as_dict"):
        data = meta.as_dict()
        return data if isinstance(data, dict) else {}
    fields = (
        "title",
        "author",
        "description",
        "sitename",
        "date",
        "categories",
        "tags",
        "language",
        "image",
    )
    return {name: getattr(meta, name, None) for name in fields}


def _word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def _extract_images(html: str, base_url: str, limit: int = 30) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()
    for match in _IMG_RE.finditer(html):
        src = urljoin(base_url, match.group(1).strip())
        if src.startswith(("http://", "https://")) and src not in seen:
            seen.add(src)
            images.append(src)
            if len(images) >= limit:
                break
    return images


def _extract_links(html: str, base_url: str, limit: int = 50) -> list[LinkItem]:
    links: list[LinkItem] = []
    seen: set[str] = set()
    for match in _A_RE.finditer(html):
        href = urljoin(base_url, match.group(1).strip())
        text = _clean(re.sub(r"<[^>]+>", "", match.group(2))) or ""
        if href.startswith(("http://", "https://")) and href not in seen:
            seen.add(href)
            links.append(LinkItem(text=text, url=href))
            if len(links) >= limit:
                break
    return links


def parse_html(
    page: FetchedPage,
    *,
    include_images: bool = True,
    include_links: bool = False,
    render_used: str = "static",
    from_cache: bool = False,
    fetched_at: Any = None,
    duration_ms: int = 0,
) -> ParseResponse:
    from datetime import datetime, timezone

    html = page.html
    url = page.final_url or page.url

    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=include_links,
        include_images=include_images,
        favor_precision=True,
        output_format="txt",
    )
    markdown = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=include_links,
        include_images=include_images,
        favor_precision=True,
        output_format="markdown",
    )

    meta_raw = _meta_from_trafilatura(html, url)
    og = _extract_og_tags(html)

    try:
        as_json = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            output_format="json",
            with_metadata=True,
        )
        if as_json:
            json_meta = json.loads(as_json)
            if isinstance(json_meta, dict):
                for key in ("title", "author", "date", "description", "sitename", "language", "image"):
                    if not meta_raw.get(key) and json_meta.get(key):
                        meta_raw[key] = json_meta[key]
                if not text and json_meta.get("text"):
                    text = json_meta["text"]
    except Exception:
        pass

    title = (
        _clean(meta_raw.get("title"))
        or _clean(og.get("og:title"))
        or _clean(og.get("twitter:title"))
        or _clean(og.get("title"))
    )
    description = (
        _clean(meta_raw.get("description"))
        or _clean(og.get("og:description"))
        or _clean(og.get("twitter:description"))
        or _clean(og.get("description"))
    )
    author = _clean(meta_raw.get("author")) or _clean(og.get("author"))
    published_date = _clean(meta_raw.get("date"))
    site_name = _clean(meta_raw.get("sitename")) or _clean(og.get("og:site_name"))
    language = _clean(meta_raw.get("language")) or _clean(og.get("og:locale"))
    if language and "_" in language:
        language = language.split("_", 1)[0].lower()
    main_image = (
        _clean(meta_raw.get("image"))
        or _clean(og.get("og:image"))
        or _clean(og.get("twitter:image"))
    )

    images = _extract_images(html, url) if include_images else []
    if main_image and main_image not in images and include_images:
        images.insert(0, main_image)
    links = _extract_links(html, url) if include_links else []

    return ParseResponse(
        url=page.url,
        final_url=page.final_url,
        title=title,
        description=description,
        author=author,
        published_date=published_date,
        site_name=site_name,
        language=language,
        main_image=main_image,
        images=images,
        links=links,
        content_markdown=markdown,
        content_text=text,
        word_count=_word_count(text),
        render_used=render_used,  # type: ignore[arg-type]
        from_cache=from_cache,
        fetched_at=fetched_at or datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )


def parse_html_string(
    html: str,
    url: str = "https://example.com/",
    *,
    include_images: bool = True,
    include_links: bool = False,
) -> ParseResponse:
    page = FetchedPage(
        url=url,
        final_url=url,
        html=html,
        content_type="text/html",
        encoding="utf-8",
        status=200,
    )
    return parse_html(page, include_images=include_images, include_links=include_links)

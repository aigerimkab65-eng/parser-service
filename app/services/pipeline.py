"""Оркестрация: static → при необходимости browser (раздел 5 ТЗ)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.errors import AppError
from app.schemas import ParseRequest, ParseResponse, RenderMode
from app.security.ssrf import validate_url_for_fetch
from app.services.browser import fetch_page_with_browser, playwright_available
from app.services.cache import parse_cache
from app.services.fetch import FetchedPage, fetch_page
from app.services.parse import parse_html
from app.services.robots import is_allowed_by_robots

logger = logging.getLogger("parser-service.pipeline")


def cache_key(url: str, render: RenderMode, include_images: bool, include_links: bool) -> str:
    payload = {
        "url": url,
        "render": render,
        "include_images": include_images,
        "include_links": include_links,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text_len(result: ParseResponse) -> int:
    return len((result.content_text or "").strip())


def _has_content(result: ParseResponse) -> bool:
    return bool(
        (result.content_text or "").strip()
        or (result.content_markdown or "").strip()
        or (result.title or "").strip()
    )


async def _extract(page: FetchedPage, req: ParseRequest, render_used: str) -> ParseResponse:
    """Trafilatura в отдельном потоке — не блокирует event loop Hypercorn."""
    return await asyncio.to_thread(
        parse_html,
        page,
        include_images=req.include_images,
        include_links=req.include_links,
        render_used=render_used,
        from_cache=False,
        fetched_at=datetime.now(timezone.utc),
        duration_ms=0,
    )


async def parse_one(req: ParseRequest, settings: Settings | None = None) -> ParseResponse:
    settings = settings or get_settings()
    url = str(req.url)
    validate_url_for_fetch(url)

    if not await is_allowed_by_robots(url, settings):
        raise AppError(
            "ROBOTS_DISALLOWED",
            "Доступ к странице запрещён правилами robots.txt",
            status_code=403,
        )

    started = time.perf_counter()
    key = cache_key(url, req.render, req.include_images, req.include_links)

    if req.use_cache:
        cached = parse_cache.get(key)
        if cached is not None:
            data = dict(cached)
            data["from_cache"] = True
            return ParseResponse.model_validate(data)

    browser_ready = settings.browser_enabled and playwright_available()
    force_browser = req.render == "always" and browser_ready
    allow_browser_fallback = req.render == "auto" and browser_ready

    if req.render == "always" and not browser_ready:
        force_browser = False

    render_used = "static"
    if force_browser:
        page = await fetch_page_with_browser(url, settings)
        render_used = "browser"
    else:
        page = await fetch_page(url, settings)

    result = await _extract(page, req, render_used)

    if (
        allow_browser_fallback
        and render_used == "static"
        and _text_len(result) < settings.min_text_chars
    ):
        logger.info("auto: текст короче %s — включаем браузер", settings.min_text_chars)
        try:
            browser_page = await fetch_page_with_browser(url, settings)
            browser_result = await _extract(browser_page, req, "browser")
            if _has_content(browser_result):
                result = browser_result
        except AppError as exc:
            if not _has_content(result):
                raise
            logger.warning("browser fallback failed (%s), отдаём static", exc.code)

    if not _has_content(result) or (
        _text_len(result) == 0 and not result.title and not result.content_markdown
    ):
        # Ошибки НЕ кэшируем
        raise AppError(
            "EMPTY_CONTENT",
            "Текст извлечь не удалось",
            status_code=422,
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    result = result.model_copy(update={"duration_ms": duration_ms, "from_cache": False})

    # Кэшируем только успешный результат
    if req.use_cache:
        parse_cache.set(key, result.model_dump(mode="json"))

    logger.info(
        "parsed url=%s render_used=%s duration_ms=%s from_cache=false",
        url,
        result.render_used,
        duration_ms,
    )
    return result

"""Браузерный режим Playwright: SSRF на все запросы; SW и WebSocket блокируются."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings, get_settings
from app.errors import AppError
from app.security.ssrf import validate_url_for_fetch
from app.services.fetch import FetchedPage

logger = logging.getLogger("parser-service.browser")

_playwright_ready: bool | None = None
_browser_semaphore: asyncio.Semaphore | None = None


def playwright_available() -> bool:
    global _playwright_ready
    if _playwright_ready is not None:
        return _playwright_ready
    try:
        import playwright  # noqa: F401

        _playwright_ready = True
    except ImportError:
        _playwright_ready = False
    return _playwright_ready


def _get_semaphore(max_pages: int) -> asyncio.Semaphore:
    global _browser_semaphore
    if _browser_semaphore is None:
        _browser_semaphore = asyncio.Semaphore(max_pages)
    return _browser_semaphore


def require_playwright(settings: Settings) -> None:
    if not settings.browser_enabled or not playwright_available():
        raise AppError(
            "FETCH_FAILED",
            "Браузерный режим недоступен. Соберите образ full и включите BROWSER_ENABLED=true.",
            status_code=502,
        )


async def fetch_page_with_browser(url: str, settings: Settings | None = None) -> FetchedPage:
    settings = settings or get_settings()
    require_playwright(settings)

    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeout
    from playwright.async_api import async_playwright

    start_url = validate_url_for_fetch(str(url))
    timeout_ms = int(settings.browser_timeout_s * 1000)
    sem = _get_semaphore(settings.browser_max_pages)

    async with sem:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    context = await browser.new_context(
                        user_agent=settings.user_agent,
                        locale="ru-RU",
                        java_script_enabled=True,
                        service_workers="block",
                    )

                    async def on_route(route: Any) -> None:
                        request_url = route.request.url
                        if request_url.startswith(("about:", "data:", "blob:")):
                            await route.continue_()
                            return
                        try:
                            validate_url_for_fetch(request_url)
                        except AppError:
                            logger.info(
                                "playwright abort SSRF url=%s type=%s",
                                request_url,
                                route.request.resource_type,
                            )
                            await route.abort()
                            return
                        await route.continue_()

                    await context.route("**/*", on_route)

                    # Блокируем все WebSocket
                    def on_web_socket(ws: Any) -> None:
                        logger.info("playwright close websocket url=%s", getattr(ws, "url", ""))
                        ws.close()

                    await context.route_web_socket("**/*", on_web_socket)

                    page = await context.new_page()
                    response = await page.goto(
                        start_url,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    try:
                        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    except PlaywrightTimeout:
                        pass

                    final_url = page.url
                    if final_url.startswith(("http://", "https://")):
                        validate_url_for_fetch(final_url)

                    if response is not None and response.status >= 400:
                        raise AppError(
                            "FETCH_FAILED",
                            f"Сайт вернул статус {response.status}",
                            status_code=502,
                        )

                    html = await page.content()
                    if len(html.encode("utf-8", errors="ignore")) > settings.max_page_bytes:
                        raise AppError(
                            "TOO_LARGE",
                            "Страница больше лимита размера",
                            status_code=413,
                        )

                    content_type = "text/html"
                    if response is not None:
                        raw_ct = (response.headers.get("content-type") or "").split(";", 1)[0].strip()
                        if raw_ct:
                            content_type = raw_ct.lower()

                    return FetchedPage(
                        url=str(url),
                        final_url=final_url,
                        html=html,
                        content_type=content_type,
                        encoding="utf-8",
                        status=response.status if response is not None else 200,
                    )
                finally:
                    await browser.close()
        except AppError:
            raise
        except PlaywrightTimeout as exc:
            raise AppError(
                "FETCH_TIMEOUT",
                f"Страница не ответила за {int(settings.browser_timeout_s)} секунд",
                status_code=504,
            ) from exc
        except PlaywrightError as exc:
            logger.warning("playwright error: %s", exc)
            raise AppError(
                "FETCH_FAILED",
                "Ошибка браузерной загрузки страницы",
                status_code=502,
            ) from exc

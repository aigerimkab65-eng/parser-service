"""Тестовая панель: POST /ui/parse без X-API-Key (только при UI_ENABLED).

Ограничения надёжности:
- браузер только если BROWSER_ENABLED и Playwright доступен;
- можно включить картинки и отключить кэш;
- cross-site вызовы из браузера отклоняются;
- rate limit по IP (с учётом X-Forwarded-For за Caddy).
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, HttpUrl

from app.config import get_settings
from app.errors import AppError
from app.schemas import ParseRequest, ParseResponse, RenderMode
from app.security.rate_limit import rate_limiter
from app.services.browser import playwright_available
from app.services.pipeline import parse_one

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)


class UiParseRequest(BaseModel):
    """Тело для UI: url + простые опции для новичка."""

    url: HttpUrl
    include_images: bool = True
    use_cache: bool = False
    use_browser: bool = False


def _client_ip(request: Request) -> str:
    """IP для лимита: за Caddy берём первый X-Forwarded-For, иначе peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _origin_host(origin: str) -> str | None:
    try:
        parsed = urlparse(origin)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    if parsed.port and parsed.port not in {80, 443}:
        return f"{host}:{parsed.port}"
    return host


async def enforce_ui_guards(request: Request) -> None:
    """Rate limit + блокировка cross-site запросов из браузера."""
    settings = get_settings()
    rate_limiter.check(f"ui:{_client_ip(request)}", settings.rate_limit_per_min)

    site = (request.headers.get("sec-fetch-site") or "").lower()
    if site == "cross-site":
        raise AppError(
            "FORBIDDEN",
            "Запрос с другого сайта запрещён",
            status_code=403,
        )

    origin = request.headers.get("origin")
    if origin:
        origin_host = _origin_host(origin)
        req_host = (request.headers.get("host") or "").split(",")[0].strip().lower()
        if req_host.endswith(":443") or req_host.endswith(":80"):
            req_host = req_host.rsplit(":", 1)[0]
        if not origin_host or origin_host != req_host:
            raise AppError(
                "FORBIDDEN",
                "Origin не совпадает с хостом сервиса",
                status_code=403,
            )


def _resolve_render(use_browser: bool) -> RenderMode:
    """Для новичка: если браузер просят, но он недоступен — тихо идём в static."""
    settings = get_settings()
    if use_browser and settings.browser_enabled and playwright_available():
        return "always"
    return "never"



@router.post("/parse", response_model=ParseResponse, dependencies=[Depends(enforce_ui_guards)])
async def ui_parse(body: UiParseRequest) -> ParseResponse:
    """Парсинг из UI: ключ не нужен."""
    req = ParseRequest(
        url=body.url,
        render=_resolve_render(body.use_browser),
        include_images=body.include_images,
        include_links=False,
        use_cache=body.use_cache,
    )
    return await parse_one(req)

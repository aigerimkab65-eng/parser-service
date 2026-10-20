"""Проверка robots.txt через ту же SSRF-защищённую загрузку."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from app.config import Settings, get_settings
from app.security.ssrf import make_safe_connector, validate_url_for_fetch

logger = logging.getLogger("parser-service.robots")

# Лимит на robots.txt (распакованные байты); лишнее отбрасывается
ROBOTS_MAX_BYTES = 500 * 1024

# Простой кэш robots.txt на время процесса (не путать с кэшем парсинга)
_robots_cache: dict[str, RobotFileParser] = {}


async def read_robots_body(content: object, max_bytes: int = ROBOTS_MAX_BYTES) -> bytes:
    """Читает тело robots.txt циклом; обрезка по max_bytes, без TOO_LARGE."""
    chunks: list[bytes] = []
    total = 0
    while total < max_bytes:
        chunk = await content.read(min(65_536, max_bytes - total))  # type: ignore[attr-defined]
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


async def fetch_robots_txt(base_url: str, settings: Settings | None = None) -> RobotFileParser:
    """Загружает /robots.txt того же origin через SSRF-safe aiohttp."""
    import aiohttp

    settings = settings or get_settings()
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(origin + "/", "robots.txt")

    if origin in _robots_cache:
        return _robots_cache[origin]

    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        validate_url_for_fetch(robots_url)
        timeout = aiohttp.ClientTimeout(total=min(settings.fetch_timeout_s, 5.0))
        headers = {"User-Agent": settings.user_agent}
        connector = make_safe_connector()
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            connector=connector,
        ) as session:
            async with session.get(robots_url, allow_redirects=False) as response:
                if response.status != 200:
                    # Нет robots / недоступен → разрешаем (стандартная практика)
                    rp.parse([])
                else:
                    raw = await read_robots_body(response.content, ROBOTS_MAX_BYTES)
                    if len(raw) >= ROBOTS_MAX_BYTES:
                        logger.info(
                            "robots.txt для %s обрезан до %s байт",
                            origin,
                            ROBOTS_MAX_BYTES,
                        )
                    text = raw.decode("utf-8", errors="replace")
                    rp.parse(text.splitlines())
    except Exception as exc:
        logger.info("robots.txt недоступен для %s (%s) — считаем разрешённым", origin, exc)
        rp.parse([])

    _robots_cache[origin] = rp
    return rp


async def is_allowed_by_robots(url: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.respect_robots:
        return True
    rp = await fetch_robots_txt(url, settings)
    return bool(rp.can_fetch(settings.user_agent, url))


def clear_robots_cache() -> None:
    _robots_cache.clear()

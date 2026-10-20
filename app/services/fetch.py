"""Быстрая загрузка страниц через aiohttp (раздел 5 ТЗ)."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp
from charset_normalizer import from_bytes
from yarl import URL

from app.config import Settings, get_settings
from app.errors import AppError
from app.security.ssrf import make_safe_connector, validate_url_for_fetch

HTML_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
    }
)


@dataclass
class FetchedPage:
    url: str
    final_url: str
    html: str
    content_type: str | None
    encoding: str | None
    status: int


def _base_content_type(header: str | None) -> str | None:
    if not header:
        return None
    return header.split(";", 1)[0].strip().lower()


def _decode_body(raw: bytes, content_type_header: str | None) -> tuple[str, str | None]:
    """Декодирует тело. Обрыв mid-UTF-8 (лимит размера / сеть) — errors=replace, без кракозябр-паники."""
    if content_type_header:
        parts = [p.strip() for p in content_type_header.split(";")]
        for part in parts[1:]:
            if part.lower().startswith("charset="):
                charset = part.split("=", 1)[1].strip().strip("\"'")
                try:
                    return raw.decode(charset), charset.lower()
                except LookupError:
                    break
                except UnicodeDecodeError:
                    # Неполный последний символ при обрезке — всё равно декодируем
                    return raw.decode(charset, errors="replace"), charset.lower()

    result = from_bytes(raw).best()
    if result is not None:
        return str(result), result.encoding

    return raw.decode("utf-8", errors="replace"), "utf-8"


async def read_body_limited(response: aiohttp.ClientResponse, max_bytes: int) -> bytes:
    """Читает тело ответа чанками с лимитом по РАСПАКОВАННЫМ байтам.

    aiohttp при ``auto_decompress=True`` (по умолчанию) отдаёт в
    ``response.content`` уже разжатый поток (gzip/deflate/br). Поэтому
    ``total`` — размер после распаковки, а не сжатый Content-Length.

    Как только накоплено ``max_bytes + 1`` байт — чтение останавливается
    и бросается ``TOO_LARGE`` (gzip-бомба не раздувает память целиком).
    Один ``content.read(n)`` на сжатых ответах часто возвращает неполный
    поток (``at_eof=False``), поэтому читаем циклом.
    """
    chunks: list[bytes] = []
    total = 0
    limit = max_bytes + 1
    while total < limit:
        chunk = await response.content.read(min(65_536, limit - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    if total > max_bytes:
        raise AppError(
            "TOO_LARGE",
            "Страница больше лимита размера",
            status_code=413,
        )
    return b"".join(chunks)


async def fetch_page(url: str, settings: Settings | None = None) -> FetchedPage:
    settings = settings or get_settings()
    current = validate_url_for_fetch(str(url))
    timeout = aiohttp.ClientTimeout(total=settings.fetch_timeout_s)
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en;q=0.8",
    }

    redirects = 0
    connector = make_safe_connector()
    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers,
        connector=connector,
    ) as session:
        while True:
            try:
                # allow_redirects=False — каждый шаг проверяем вручную (SSRF)
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            raise AppError(
                                "FETCH_FAILED",
                                "Редирект без заголовка Location",
                                status_code=502,
                            )
                        next_url = str(response.url.join(URL(location, encoded=True)))
                        redirects += 1
                        if redirects > settings.max_redirects:
                            raise AppError(
                                "FETCH_FAILED",
                                "Слишком много переадресаций",
                                status_code=502,
                            )
                        current = validate_url_for_fetch(next_url)
                        continue

                    if response.status >= 400:
                        raise AppError(
                            "FETCH_FAILED",
                            f"Сайт вернул статус {response.status}",
                            status_code=502,
                        )

                    content_type_header = response.headers.get("Content-Type")
                    base_ct = _base_content_type(content_type_header)
                    if base_ct and base_ct not in HTML_TYPES and "html" not in base_ct:
                        raise AppError(
                            "NOT_HTML",
                            f"По ссылке не веб-страница: {base_ct}",
                            status_code=415,
                        )

                    raw = await read_body_limited(response, settings.max_page_bytes)
                    html, encoding = _decode_body(raw, content_type_header)
                    return FetchedPage(
                        url=str(url),
                        final_url=str(response.url),
                        html=html,
                        content_type=base_ct,
                        encoding=encoding,
                        status=response.status,
                    )
            except AppError:
                raise
            except TimeoutError as exc:
                raise AppError(
                    "FETCH_TIMEOUT",
                    f"Страница не ответила за {int(settings.fetch_timeout_s)} секунд",
                    status_code=504,
                ) from exc
            except OSError as exc:
                # SafeAsyncResolver бросает OSError при SSRF
                msg = str(exc)
                if "SSRF" in msg or "заблокирован" in msg or "внутренн" in msg.lower():
                    raise AppError(
                        "FORBIDDEN_HOST",
                        "Доступ к внутренним адресам запрещён",
                        status_code=403,
                    ) from exc
                raise AppError(
                    "FETCH_FAILED",
                    "Сайт недоступен или вернул ошибку",
                    status_code=502,
                ) from exc
            except aiohttp.ClientError as exc:
                raise AppError(
                    "FETCH_FAILED",
                    "Сайт недоступен или вернул ошибку",
                    status_code=502,
                ) from exc

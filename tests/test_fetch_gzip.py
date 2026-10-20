"""Чтение тела: полный gzip ~1 МБ и gzip-бомба → TOO_LARGE."""

from __future__ import annotations

import gzip
import os
from unittest.mock import patch

import aiohttp
import anyio
import pytest
from aiohttp import web

from app.config import get_settings, reset_settings_cache
from app.errors import AppError
from app.services.fetch import fetch_page, read_body_limited


def _html_about(size: int) -> bytes:
    """HTML примерно указанного размера (распакованные байты)."""
    filler = size - 40
    if filler < 1:
        filler = 1
    return b"<html><body>" + (b"A" * filler) + b"</body></html>"


async def _serve_gzip(app_handler) -> tuple[web.AppRunner, str]:
    app = web.Application()
    app.router.add_get("/", app_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # noqa: SLF001
    return runner, f"http://127.0.0.1:{port}/"


def test_gzip_page_about_1mb_read_fully() -> None:
    """gzip-страница ~1 МБ читается целиком (раньше обрезалась на ~40 КБ)."""
    plain = _html_about(1_050_000)
    compressed = gzip.compress(plain, compresslevel=6)
    assert len(compressed) < 50_000  # сжатый ответ маленький
    assert len(plain) > 1_000_000

    async def handler(_request: web.Request) -> web.Response:
        return web.Response(
            body=compressed,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Content-Encoding": "gzip",
            },
        )

    async def run() -> None:
        runner, url = await _serve_gzip(handler)
        try:
            with (
                patch("app.services.fetch.validate_url_for_fetch", side_effect=lambda u: str(u)),
                patch(
                    "app.services.fetch.make_safe_connector",
                    return_value=aiohttp.TCPConnector(),
                ),
            ):
                page = await fetch_page(url)
            raw = page.html.encode("utf-8", errors="replace")
            assert len(raw) >= 1_000_000
            assert len(raw) == len(plain) or abs(len(raw) - len(plain)) < 8
            assert "AAAA" in page.html
        finally:
            await runner.cleanup()

    anyio.run(run)


def test_gzip_bomb_too_large() -> None:
    """Маленький gzip → >5 МБ после распаковки → TOO_LARGE; пик памяти < полный объём бомбы."""
    import gc
    import tracemalloc

    os.environ["MAX_PAGE_MB"] = "5"
    reset_settings_cache()
    settings = get_settings()
    assert settings.max_page_bytes == 5 * 1024 * 1024

    bomb_plain = _html_about(8 * 1024 * 1024)
    compressed = gzip.compress(bomb_plain, compresslevel=9)
    bomb_size = len(bomb_plain)
    del bomb_plain
    gc.collect()
    assert len(compressed) < 100_000  # «бомба»: сжато мало
    assert bomb_size > settings.max_page_bytes

    async def handler(_request: web.Request) -> web.Response:
        return web.Response(
            body=compressed,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Content-Encoding": "gzip",
            },
        )

    async def run() -> None:
        runner, url = await _serve_gzip(handler)
        try:
            gc.collect()
            tracemalloc.start()
            baseline = tracemalloc.get_traced_memory()[0]
            with (
                patch("app.services.fetch.validate_url_for_fetch", side_effect=lambda u: str(u)),
                patch(
                    "app.services.fetch.make_safe_connector",
                    return_value=aiohttp.TCPConnector(),
                ),
            ):
                with pytest.raises(AppError) as exc:
                    await fetch_page(url, settings=settings)
            _cur, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            growth = peak - baseline
            assert exc.value.code == "TOO_LARGE"
            assert exc.value.status_code == 413
            # Не держим всю бомбу (8 МБ+) в RAM: max + запас на zlib/aiohttp
            assert growth < bomb_size
            assert growth < settings.max_page_bytes + 4 * 1024 * 1024
        finally:
            await runner.cleanup()

    anyio.run(run)
    os.environ.pop("MAX_PAGE_MB", None)
    reset_settings_cache()


def test_read_body_limited_stops_at_max() -> None:
    """Напрямую: после max_bytes+1 распакованных байт — TOO_LARGE."""
    max_bytes = 100_000
    plain = b"Z" * (max_bytes + 50_000)
    compressed = gzip.compress(plain)

    async def handler(_request: web.Request) -> web.Response:
        return web.Response(
            body=compressed,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Content-Encoding": "gzip",
            },
        )

    async def run() -> None:
        runner, url = await _serve_gzip(handler)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    with pytest.raises(AppError) as exc:
                        await read_body_limited(response, max_bytes)
                    assert exc.value.code == "TOO_LARGE"
                    assert exc.value.status_code == 413
        finally:
            await runner.cleanup()

    anyio.run(run)

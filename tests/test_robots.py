"""robots.txt через SSRF-safe загрузку."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from app.config import reset_settings_cache
from app.errors import AppError
from app.schemas import ParseRequest
from app.services.pipeline import parse_one
from app.services.robots import (
    ROBOTS_MAX_BYTES,
    clear_robots_cache,
    is_allowed_by_robots,
    read_robots_body,
)


class _ByteStream:
    """Поток: отдаёт данные порциями, затем b''."""

    def __init__(self, data: bytes, chunk_size: int = 8192) -> None:
        self._data = data
        self._pos = 0
        self._chunk_size = chunk_size

    async def read(self, n: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        if n < 0:
            n = self._chunk_size
        n = min(n, self._chunk_size, len(self._data) - self._pos)
        out = self._data[self._pos : self._pos + n]
        self._pos += len(out)
        return out


def test_robots_disallow() -> None:
    clear_robots_cache()
    os.environ["RESPECT_ROBOTS"] = "true"
    reset_settings_cache()

    robots_body = b"User-agent: *\nDisallow: /private\n"
    stream = _ByteStream(robots_body)

    class FakeResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @property
        def content(self):
            return stream

    class FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def get(self, url, allow_redirects=False):
            return FakeResp()

    async def run() -> None:
        with (
            patch(
                "app.services.robots.validate_url_for_fetch",
                return_value="https://example.com/robots.txt",
            ),
            patch("app.services.robots.make_safe_connector", return_value=MagicMock()),
            patch("aiohttp.ClientSession", FakeSession),
        ):
            assert await is_allowed_by_robots("https://example.com/public") is True
            assert await is_allowed_by_robots("https://example.com/private/secret") is False

    anyio.run(run)
    clear_robots_cache()
    os.environ["RESPECT_ROBOTS"] = "false"
    reset_settings_cache()


def test_robots_disallowed_error_code() -> None:
    async def run() -> None:
        with patch(
            "app.services.pipeline.is_allowed_by_robots",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(AppError) as exc:
                await parse_one(
                    ParseRequest(url="https://example.com/x", use_cache=False)
                )
            assert exc.value.code == "ROBOTS_DISALLOWED"
            assert exc.value.status_code == 403

    anyio.run(run)


def test_robots_body_truncated_at_500kb() -> None:
    """Тело больше 500 КБ — читаем ровно лимит, лишнее отбрасываем."""
    assert ROBOTS_MAX_BYTES == 500 * 1024
    oversized = b"A" * (ROBOTS_MAX_BYTES + 50_000)

    async def run() -> None:
        raw = await read_robots_body(_ByteStream(oversized, chunk_size=32_768))
        assert len(raw) == ROBOTS_MAX_BYTES
        assert raw == b"A" * ROBOTS_MAX_BYTES

    anyio.run(run)


def test_robots_oversized_still_parses_prefix() -> None:
    """В начале файла — правило Disallow; хвост обрезается, правило сохраняется."""
    clear_robots_cache()
    os.environ["RESPECT_ROBOTS"] = "true"
    reset_settings_cache()

    header = b"User-agent: *\nDisallow: /secret\n"
    padding = b"# " + b"x" * (ROBOTS_MAX_BYTES)  # заведомо больше лимита вместе с header
    body = header + padding
    stream = _ByteStream(body)

    class FakeResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @property
        def content(self):
            return stream

    class FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def get(self, url, allow_redirects=False):
            return FakeResp()

    async def run() -> None:
        with (
            patch(
                "app.services.robots.validate_url_for_fetch",
                return_value="https://example.com/robots.txt",
            ),
            patch("app.services.robots.make_safe_connector", return_value=MagicMock()),
            patch("aiohttp.ClientSession", FakeSession),
        ):
            assert await is_allowed_by_robots("https://example.com/ok") is True
            assert await is_allowed_by_robots("https://example.com/secret/x") is False

    anyio.run(run)
    clear_robots_cache()
    os.environ["RESPECT_ROBOTS"] = "false"
    reset_settings_cache()

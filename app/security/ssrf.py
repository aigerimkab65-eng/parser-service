"""Защита от SSRF: разрешены только глобально маршрутизируемые IP."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import aiohttp
from aiohttp.resolver import DefaultResolver

from app.config import get_settings
from app.errors import AppError

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
    }
)

_INTERNAL_MSG = "Доступ к внутренним адресам запрещён"


def normalize_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Сводит ::ffff:x.x.x.x к IPv4."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Блокируем всё, что не is_global, плюс multicast/reserved/unspecified."""
    ip = normalize_ip(ip)
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    # Основное правило ТЗ: разрешать только глобально маршрутизируемые адреса
    return not ip.is_global


def _hostname_is_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def assert_ip_allowed(ip_str: str) -> None:
    ip = ipaddress.ip_address(ip_str)
    if is_blocked_ip(ip):
        raise AppError("FORBIDDEN_HOST", _INTERNAL_MSG, status_code=403)


def validate_url_for_fetch(url: str) -> str:
    """Проверяет URL: схема, порт, DNS → только глобальные IP."""
    settings = get_settings()
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise AppError(
            "INVALID_URL",
            "Разрешены только схемы http и https",
            status_code=422,
        )
    if not parsed.hostname:
        raise AppError("INVALID_URL", "В URL отсутствует хост", status_code=422)

    hostname = parsed.hostname.lower().rstrip(".")

    # Сначала hostname/IP — чтобы 127.0.0.1 давал «внутренний адрес», а не «порт»
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise AppError("FORBIDDEN_HOST", _INTERNAL_MSG, status_code=403)

    literal_ip = _hostname_is_ip(hostname)
    if literal_ip is not None:
        if is_blocked_ip(literal_ip):
            raise AppError("FORBIDDEN_HOST", _INTERNAL_MSG, status_code=403)
    else:
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise AppError(
                "FETCH_FAILED",
                f"Не удалось разрешить хост: {hostname}",
                status_code=502,
            ) from exc
        if not addr_infos:
            raise AppError(
                "FETCH_FAILED",
                f"Не удалось разрешить хост: {hostname}",
                status_code=502,
            )
        for info in addr_infos:
            assert_ip_allowed(info[4][0])

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if port not in settings.allowed_ports:
        raise AppError(
            "FORBIDDEN_HOST",
            f"Порт {port} запрещён",
            status_code=403,
        )

    return url


class SafeAsyncResolver(DefaultResolver):
    """Резолвер aiohttp: проверка IP при каждом resolve (защита от DNS rebinding)."""

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: int = socket.AF_UNSPEC,
    ) -> list[dict[str, Any]]:
        hosts = await super().resolve(host, port, family)
        safe: list[dict[str, Any]] = []
        for item in hosts:
            host_ip = item.get("host")
            if host_ip is None:
                continue
            try:
                assert_ip_allowed(str(host_ip))
            except AppError as exc:
                raise OSError(exc.message) from exc
            safe.append(item)
        if not safe:
            raise OSError(_INTERNAL_MSG)
        return safe


def make_safe_connector() -> aiohttp.TCPConnector:
    return aiohttp.TCPConnector(resolver=SafeAsyncResolver(), ssl=True)

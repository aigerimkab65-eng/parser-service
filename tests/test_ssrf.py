"""Защита от внутренних адресов → FORBIDDEN_HOST (внутренний адрес)."""

from __future__ import annotations

import ipaddress
import socket
from unittest.mock import patch

import anyio
import pytest

from app.errors import AppError
from app.security.ssrf import SafeAsyncResolver, is_blocked_ip, normalize_ip, validate_url_for_fetch


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/admin",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "http://10.0.0.5/secret",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://172.16.5.1/",
        "http://100.64.0.1/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
def test_forbidden_hosts_message_is_internal(url: str) -> None:
    with pytest.raises(AppError) as exc:
        validate_url_for_fetch(url)
    assert exc.value.code in {"FORBIDDEN_HOST", "INVALID_URL"}
    if exc.value.code == "FORBIDDEN_HOST":
        assert "Порт" not in exc.value.message
        assert "внутренн" in exc.value.message.lower()


def test_ipv4_mapped_and_cgnat() -> None:
    assert is_blocked_ip(normalize_ip(ipaddress.ip_address("::ffff:127.0.0.1")))
    assert is_blocked_ip(ipaddress.ip_address("100.64.0.1"))
    assert not is_blocked_ip(ipaddress.ip_address("8.8.8.8"))


def test_non_standard_port_after_public_dns() -> None:
    public = [(2, 1, 6, "", ("93.184.216.34", 0))]
    with patch("app.security.ssrf.socket.getaddrinfo", return_value=public):
        with pytest.raises(AppError) as exc:
            validate_url_for_fetch("https://example.com:8080/")
    assert exc.value.code == "FORBIDDEN_HOST"
    assert "Порт" in exc.value.message


def test_redirect_to_internal_blocked() -> None:
    internal = [(2, 1, 6, "", ("192.168.0.10", 0))]
    with patch("app.security.ssrf.socket.getaddrinfo", return_value=internal):
        with pytest.raises(AppError) as exc:
            validate_url_for_fetch("https://evil.example/")
    assert exc.value.code == "FORBIDDEN_HOST"
    assert "Порт" not in exc.value.message


def test_allows_public_https() -> None:
    public = [(2, 1, 6, "", ("93.184.216.34", 0))]
    with patch("app.security.ssrf.socket.getaddrinfo", return_value=public):
        url = validate_url_for_fetch("https://example.com/page")
    assert url.startswith("https://")


def test_dns_rebinding_second_resolve_blocked() -> None:
    """Первый resolve — публичный IP, второй — 127.0.0.1 → блокировка."""
    calls = {"n": 0}

    async def fake_super_resolve(self, host, port=0, family=socket.AF_UNSPEC):
        calls["n"] += 1
        ip = "93.184.216.34" if calls["n"] == 1 else "127.0.0.1"
        return [
            {
                "hostname": host,
                "host": ip,
                "port": port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
        ]

    async def run() -> None:
        resolver = SafeAsyncResolver()
        with patch("app.security.ssrf.DefaultResolver.resolve", new=fake_super_resolve):
            first = await resolver.resolve("rebinding.example", 80)
            assert first[0]["host"] == "93.184.216.34"
            with pytest.raises(OSError) as exc:
                await resolver.resolve("rebinding.example", 80)
            assert "внутренн" in str(exc.value).lower()

    anyio.run(run)

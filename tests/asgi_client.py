"""Минимальный синхронный ASGI-клиент для тестов (без httpx)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anyio


@dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


class ASGIClient:
    def __init__(self, app: Any) -> None:
        self.app = app

    def get(self, path: str, headers: dict[str, str] | None = None) -> Response:
        return anyio.run(self._request, "GET", path, headers, None)

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Response:
        return anyio.run(self._request, "POST", path, headers, json)

    async def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None,
        json_body: dict[str, Any] | None,
    ) -> Response:
        body_bytes = b""
        header_list: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            header_list.append((b"content-type", b"application/json"))
            header_list.append((b"content-length", str(len(body_bytes)).encode("ascii")))
        if headers:
            for key, value in headers.items():
                header_list.append((key.lower().encode("latin-1"), value.encode("latin-1")))

        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": header_list,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }

        sent_body = False

        async def receive() -> dict[str, Any]:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        status_code = 500
        response_headers: dict[str, str] = {}
        chunks: list[bytes] = []

        async def send(message: dict[str, Any]) -> None:
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b"") or b"")

        await self.app(scope, receive, send)
        return Response(status_code=status_code, headers=response_headers, content=b"".join(chunks))

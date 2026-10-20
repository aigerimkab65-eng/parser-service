#!/usr/bin/env python3
"""Минимальный клиент parser-service (stdlib + urllib)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def parse(url: str, *, base: str, api_key: str) -> dict:
    body = json.dumps({"url": url, "render": "never"}).encode("utf-8")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/v1/parse",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("Задайте API_KEY", file=sys.stderr)
        return 2
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
    try:
        data = parse(target, base=base, api_key=api_key)
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

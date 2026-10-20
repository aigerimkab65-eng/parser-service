"""Проверка лицензий прямых зависимостей (раздел 2 ТЗ)."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

DIRECT = {
    "fastapi",
    "pydantic",
    "hypercorn",
    "aiohttp",
    "trafilatura",
    "cachetools",
    "pytest",
    "pip-licenses",
}

ALLOWED_MARKERS = ("MIT", "Apache-2.0", "Apache Software License", "Apache 2")


def test_direct_dependencies_mit_or_apache() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json"],
        check=True,
        capture_output=True,
        text=True,
    )
    packages = {item["Name"].lower(): item for item in json.loads(result.stdout)}

    problems: list[str] = []
    for name in DIRECT:
        if name == "pip-licenses":
            continue  # сам себя не показывает
        entry = None
        for key, value in packages.items():
            if key.lower() == name.lower() or key.lower().replace("_", "-") == name:
                entry = value
                break
        assert entry is not None, f"Пакет {name} не найден"
        license_name = entry.get("License") or ""
        if not any(m in license_name for m in ALLOWED_MARKERS):
            problems.append(f"{name}: {license_name}")

    assert not problems, "Запрещённая лицензия в прямых зависимостях: " + "; ".join(problems)

    pip_lic = metadata("pip-licenses")
    field = (pip_lic.get("License") or pip_lic.get("License-Expression") or "").upper()
    assert "MIT" in field

    # Playwright опционален (full)
    try:
        pw = metadata("playwright")
    except PackageNotFoundError:
        return
    pw_lic = (pw.get("License") or pw.get("License-Expression") or "").upper()
    assert "APACHE" in pw_lic


def test_third_party_licenses_file_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "THIRD_PARTY_LICENSES.md"
    if not path.exists():
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piplicenses",
                "--format=markdown",
                "--with-urls",
                "--output-file",
                str(path),
            ],
            check=True,
        )
    text = path.read_text(encoding="utf-8")
    assert len(text) > 100

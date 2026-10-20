"""GET /version — публичная информация о сборке (без API-ключа)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import VersionResponse

router = APIRouter(tags=["meta"])


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        version=settings.app_version,
        commit=settings.git_commit,
        variant=settings.variant,
    )

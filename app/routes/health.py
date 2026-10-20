"""GET /health."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.schemas import HealthResponse
from app.services.browser import playwright_available

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        browser_enabled=bool(settings.browser_enabled and playwright_available()),
    )

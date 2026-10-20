"""Точка входа FastAPI-приложения."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.errors import AppError, app_error_handler, error_body, unhandled_error_handler
from app.routes import health, parse, ui, version
from app.security.headers import SecurityHeadersMiddleware
from app.security.startup import log_security_warnings
from app.services.browser import playwright_available

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("parser-service")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Только проверка настроек — никаких скачиваний при старте
    log_security_warnings(settings)
    logger.info(
        "parser-service %s (commit=%s) started (variant=%s, browser_enabled=%s, playwright=%s, ui=%s, app_env=%s)",
        settings.app_version,
        settings.git_commit,
        settings.variant,
        settings.browser_enabled,
        playwright_available(),
        settings.ui_enabled,
        settings.app_env,
    )
    yield


app = FastAPI(
    title="parser-service",
    version=settings.app_version or __version__,
    description="HTTP-сервис парсинга веб-страниц по ссылке.",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body("INVALID_URL", "Некорректный запрос или URL"),
    )


app.include_router(health.router)
app.include_router(version.router)
app.include_router(parse.router)

if settings.ui_enabled and STATIC_DIR.is_dir():
    app.include_router(ui.router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def ui_index() -> FileResponse:
        # HTML без долгого кэша — иначе браузер держит старый app.js
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-store"},
        )

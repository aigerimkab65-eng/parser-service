"""Pydantic-схемы запросов и ответов (раздел 4 ТЗ)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

RenderMode = Literal["auto", "never", "always"]
RenderUsed = Literal["static", "browser"]


class ParseRequest(BaseModel):
    url: HttpUrl
    render: RenderMode = "auto"
    include_images: bool = True
    include_links: bool = False
    use_cache: bool = True


class ParseBatchRequest(BaseModel):
    urls: list[HttpUrl] = Field(..., min_length=1, max_length=10)
    render: RenderMode = "auto"
    include_images: bool = True
    include_links: bool = False
    use_cache: bool = True

    @field_validator("urls")
    @classmethod
    def unique_not_required(cls, value: list[HttpUrl]) -> list[HttpUrl]:
        return value


class LinkItem(BaseModel):
    text: str
    url: str


class ParseResponse(BaseModel):
    url: str
    final_url: str
    title: str | None = None
    description: str | None = None
    author: str | None = None
    published_date: str | None = None
    site_name: str | None = None
    language: str | None = None
    main_image: str | None = None
    images: list[str] = Field(default_factory=list)
    links: list[LinkItem] = Field(default_factory=list)
    content_markdown: str | None = None
    content_text: str | None = None
    word_count: int = 0
    render_used: RenderUsed = "static"
    from_cache: bool = False
    fetched_at: datetime
    duration_ms: int = 0


class BatchItemResult(BaseModel):
    ok: bool
    data: ParseResponse | None = None
    error: dict[str, str] | None = None


class ParseBatchResponse(BaseModel):
    results: list[BatchItemResult]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    browser_enabled: bool = False


class VersionResponse(BaseModel):
    version: str
    commit: str
    variant: str

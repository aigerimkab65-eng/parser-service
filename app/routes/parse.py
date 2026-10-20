"""POST /v1/parse и POST /v1/parse/batch."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.errors import AppError
from app.schemas import (
    BatchItemResult,
    ParseBatchRequest,
    ParseBatchResponse,
    ParseRequest,
    ParseResponse,
)
from app.security.api_key import require_api_key
from app.security.rate_limit import enforce_rate_limit
from app.services.pipeline import parse_one

router = APIRouter(prefix="/v1", tags=["parse"])


@router.post(
    "/parse",
    response_model=ParseResponse,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
async def parse_url(body: ParseRequest) -> ParseResponse:
    return await parse_one(body)


@router.post(
    "/parse/batch",
    response_model=ParseBatchResponse,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
async def parse_batch(body: ParseBatchRequest) -> ParseBatchResponse:
    """До 10 ссылок за раз (этап 2)."""

    async def one(url) -> BatchItemResult:
        req = ParseRequest(
            url=url,
            render=body.render,
            include_images=body.include_images,
            include_links=body.include_links,
            use_cache=body.use_cache,
        )
        try:
            data = await parse_one(req)
            return BatchItemResult(ok=True, data=data)
        except AppError as exc:
            return BatchItemResult(
                ok=False,
                error={"code": exc.code, "message": exc.message},
            )

    results = await asyncio.gather(*(one(u) for u in body.urls))
    return ParseBatchResponse(results=list(results))

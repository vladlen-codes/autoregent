import logging
import time

import httpx
from fastapi import APIRouter, Request, Response

from app.config import settings
from app.logging_config import log_event

logger = logging.getLogger("candor.proxy")
router = APIRouter()

# Headers that must not be blindly forwarded in either direction of a proxy hop.
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
}


def _filter_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    """Phase 1: straight passthrough. No healing, no classification yet."""
    target_url = f"{settings.upstream_base_url}/{path}"
    body = await request.body()
    forward_headers = _filter_headers(request.headers)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as client:
            upstream_response = await client.request(
                request.method,
                target_url,
                content=body,
                headers=forward_headers,
                params=request.query_params,
            )
    except httpx.TimeoutException:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log_event(logger, logging.WARNING, "upstream_timeout", target=target_url, duration_ms=duration_ms)
        return Response(
            content=b'{"error":"upstream_timeout"}', status_code=504, media_type="application/json"
        )
    except httpx.HTTPError as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log_event(
            logger, logging.ERROR, "upstream_unreachable",
            target=target_url, error=str(exc), duration_ms=duration_ms,
        )
        return Response(
            content=b'{"error":"upstream_unreachable"}', status_code=502, media_type="application/json"
        )

    duration_ms = round((time.monotonic() - start) * 1000, 1)
    log_event(
        logger, logging.INFO, "proxy_dispatch",
        target=target_url, status_code=upstream_response.status_code, duration_ms=duration_ms,
    )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_filter_headers(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
    )

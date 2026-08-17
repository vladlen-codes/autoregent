import logging
import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.logging_config import log_event

logger = logging.getLogger("autoregent.dispatch")

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


def filter_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


@dataclass
class DispatchResult:
    status_code: int
    content: bytes
    headers: dict

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


async def dispatch_upstream(path: str, method: str, headers: dict, body: bytes, params) -> DispatchResult:
    target_url = f"{settings.upstream_base_url}/{path}"
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as client:
            response = await client.request(
                method, target_url, content=body, headers=filter_headers(headers), params=params
            )
    except httpx.TimeoutException:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log_event(logger, logging.WARNING, "upstream_timeout", target=target_url, duration_ms=duration_ms)
        return DispatchResult(504, b'{"error":"upstream_timeout"}', {"content-type": "application/json"})
    except httpx.HTTPError as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log_event(
            logger, logging.ERROR, "upstream_unreachable",
            target=target_url, error=str(exc), duration_ms=duration_ms,
        )
        return DispatchResult(502, b'{"error":"upstream_unreachable"}', {"content-type": "application/json"})

    duration_ms = round((time.monotonic() - start) * 1000, 1)
    log_event(
        logger, logging.INFO, "upstream_dispatch",
        target=target_url, status_code=response.status_code, duration_ms=duration_ms,
    )
    return DispatchResult(response.status_code, response.content, filter_headers(response.headers))

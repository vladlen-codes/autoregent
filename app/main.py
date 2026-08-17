import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.circuit import circuit_registry
from app.config import settings
from app.events import HealEvent, event_store
from app.logging_config import configure_logging, log_event
from app.mock_upstream import router as mock_router
from app.proxy import router as proxy_router

configure_logging(settings.log_level)
logger = logging.getLogger("autoregent")

app = FastAPI(title="Autoregent Gateway", version="0.1.0")

# /health and /events are read-only and unauthenticated by design (v0.1, single
# node, no accounts) -- the dashboard is a static GitHub Pages site on a
# different origin, so it needs the browser to allow the cross-origin GET.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(mock_router)
app.include_router(proxy_router)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    log_event(
        logger, logging.INFO, "request",
        method=request.method, path=request.url.path,
        status_code=response.status_code, duration_ms=duration_ms,
    )
    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "autoregent-gateway",
        "circuits": circuit_registry.snapshot(),
        "budget_config": {
            "max_heals_per_transaction": settings.max_heals_per_transaction,
            "rolling_window_seconds": settings.rolling_window_seconds,
            "rolling_window_max_heals": settings.rolling_window_max_heals,
            "circuit_cooldown_seconds": settings.circuit_cooldown_seconds,
        },
    }


@app.get("/events", response_model=list[HealEvent])
async def get_events():
    return event_store.all()

from fastapi import FastAPI

from ..config import AutoregentConfig
from ..gateway import Autoregent
from ..rules import RouteRules
from .mock_upstream import router as mock_router
from .models import AccountBalance

__all__ = ["build_demo_app", "AccountBalance", "mock_router"]


def build_demo_app(
    *,
    gemini_api_key: str | None = None,
    port: int = 8000,
    cors_allow_origins: list[str] | None = None,
) -> FastAPI:
    """A complete, runnable demo: the gateway and its own flaky mock upstream
    in one process -- the mock lives at /mock/*, and the gateway's
    upstream_base_url points back at this same process via localhost.

    That's deliberate, not a shortcut: several PaaS providers (Railway
    included) block a container from calling back into its own public domain
    from inside itself (a "hairpin" request rejected at the edge). Since
    they're the same process here anyway, localhost sidesteps it entirely --
    the same fix that applies to any self-hosted deployment where the gateway
    and its upstream happen to share a network boundary.
    """
    config = AutoregentConfig(
        upstream_base_url=f"http://localhost:{port}",
        gemini_api_key=gemini_api_key,
    )
    rules = RouteRules().transactional("*txn/*").expect("mock/*", AccountBalance)
    gateway = Autoregent(config=config, rules=rules, cors_allow_origins=cors_allow_origins)
    gateway.app.include_router(mock_router)
    return gateway.app

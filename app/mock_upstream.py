import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/mock", tags=["mock-upstream"])

SCENARIOS = {"healthy", "field_rename", "type_change", "timeout", "500", "cascading"}

# Mock upstream sleeps longer than the gateway's dispatch timeout so the
# scenario reliably triggers a client-side timeout rather than a slow success.
TIMEOUT_SLEEP_SECONDS = 8


def _base_payload() -> dict:
    return {
        "account_id": "acc_8841",
        "balance": 542.10,
        "currency": "USD",
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.api_route("/{scenario}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def mock_upstream(scenario: str, request: Request):
    if scenario not in SCENARIOS:
        return JSONResponse(status_code=404, content={"error": f"unknown_scenario:{scenario}"})

    if scenario == "healthy":
        return _base_payload()

    if scenario == "field_rename":
        payload = _base_payload()
        return {
            "id": payload["account_id"],
            "current_balance": payload["balance"],
            "currency": payload["currency"],
            "as_of": payload["as_of"],
        }

    if scenario == "type_change":
        payload = _base_payload()
        payload["balance"] = str(payload["balance"])
        return payload

    if scenario == "timeout":
        await asyncio.sleep(TIMEOUT_SLEEP_SECONDS)
        return _base_payload()

    if scenario == "500":
        return JSONResponse(status_code=500, content={"error": "upstream_internal_error"})

    # cascading: the primary fails, and its declared fallback target fails too.
    # Phase 2's loop detector uses this to demonstrate suppression instead of
    # an infinite retry chain.
    return JSONResponse(
        status_code=502,
        content={"error": "upstream_unavailable", "fallback_target": "mock/cascading"},
    )

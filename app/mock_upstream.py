import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["mock-upstream"])

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


async def _render_scenario(scenario: str, fallback_target: str) -> tuple[int, dict]:
    if scenario == "healthy":
        return 200, _base_payload()

    if scenario == "field_rename":
        payload = _base_payload()
        return 200, {
            "id": payload["account_id"],
            "current_balance": payload["balance"],
            "currency": payload["currency"],
            "as_of": payload["as_of"],
        }

    if scenario == "type_change":
        payload = _base_payload()
        payload["balance"] = str(payload["balance"])
        return 200, payload

    if scenario == "timeout":
        await asyncio.sleep(TIMEOUT_SLEEP_SECONDS)
        return 200, _base_payload()

    if scenario == "500":
        return 500, {"error": "upstream_internal_error"}

    # cascading: the primary fails, and its declared fallback target fails too.
    # The gateway's loop detector uses this to demonstrate suppression instead
    # of an infinite retry chain.
    return 502, {"error": "upstream_unavailable", "fallback_target": fallback_target}


@router.api_route("/mock/{scenario}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def mock_upstream(scenario: str, request: Request):
    if scenario not in SCENARIOS:
        return JSONResponse(status_code=404, content={"error": f"unknown_scenario:{scenario}"})
    status, content = await _render_scenario(scenario, fallback_target="mock/cascading")
    return JSONResponse(status_code=status, content=content)


@router.api_route("/mock/txn/{scenario}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def mock_txn_upstream(scenario: str, request: Request):
    """Same upstream behaviour, mounted where the route classifier tags the
    proxied path TRANSACTIONAL -- demonstrates that identical upstream drift
    is healed on an informational route but always fails loud here."""
    if scenario not in SCENARIOS:
        return JSONResponse(status_code=404, content={"error": f"unknown_scenario:{scenario}"})
    status, content = await _render_scenario(scenario, fallback_target="mock/txn/cascading")
    return JSONResponse(status_code=status, content=content)

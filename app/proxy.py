import logging

from fastapi import APIRouter, Request, Response

from app.circuit import CircuitState, circuit_registry
from app.dispatch import dispatch_upstream
from app.heal_pipeline import (
    handle_circuit_open,
    handle_informational_failure,
    handle_transactional_failure,
    validate_against_schema,
)
from app.logging_config import log_event
from app.route_classifier import RouteClass, classify_route
from app.transaction_context import TransactionContext

logger = logging.getLogger("candor.proxy")
router = APIRouter()


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    route_class = classify_route(path)
    ctx = TransactionContext(
        route=path,
        route_class=route_class,
        idempotency_key=request.headers.get("idempotency-key"),
    )
    circuit = circuit_registry.get(path)

    if not circuit.allow_request():
        return await handle_circuit_open(ctx)

    was_half_open = circuit.state == CircuitState.HALF_OPEN

    ctx.push(path)
    body = await request.body()
    result = await dispatch_upstream(path, request.method, dict(request.headers), body, request.query_params)

    if result.ok:
        drift = validate_against_schema(path, result.content) if route_class == RouteClass.INFORMATIONAL else None

        if drift is None:
            # Genuinely clean: only this counts as probe success. A 200 with
            # drifted content must NOT close the circuit early.
            if was_half_open:
                circuit.record_probe_result(success=True)
            return Response(content=result.content, status_code=result.status_code, headers=result.headers)

        if was_half_open:
            circuit.record_probe_result(success=False)
        log_event(logger, logging.WARNING, "schema_drift_detected", route=path, detail=drift)
        return await handle_informational_failure(
            ctx, result.status_code, result.content, result.headers, is_transport_failure=False,
        )

    if was_half_open:
        circuit.record_probe_result(success=False)

    if route_class == RouteClass.TRANSACTIONAL:
        return await handle_transactional_failure(ctx, result.status_code, result.content, result.headers)

    return await handle_informational_failure(
        ctx, result.status_code, result.content, result.headers, is_transport_failure=True,
    )

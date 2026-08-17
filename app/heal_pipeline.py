import json
import logging
from datetime import datetime, timezone

from fastapi import Response
from pydantic import ValidationError as PydanticValidationError

from app.circuit import circuit_registry
from app.config import settings
from app.dispatch import dispatch_upstream
from app.events import HealEvent, event_store
from app.logging_config import log_event
from app.route_classifier import RouteClass
from app.schema_registry import get_expected_schema
from app.transaction_context import TransactionContext

logger = logging.getLogger("candor.heal")


def _parse_json(content: bytes) -> dict | list | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def validate_against_schema(path: str, content: bytes) -> str | None:
    """Returns a description of the drift, or None if the payload matches
    the expected shape (or no shape is registered for this route)."""
    schema = get_expected_schema(path)
    if schema is None:
        return None
    if not content:
        return "response body was empty"
    try:
        # Strict + JSON mode: a stringified float ("542.1") is still rejected
        # since JSON has a native number type, but an ISO datetime string is
        # accepted since JSON has no native datetime type. model_validate()
        # on a plain dict would instead coerce both -- silently swallowing
        # exactly the kind of type drift this gate exists to catch.
        schema.model_validate_json(content, strict=True)
    except PydanticValidationError as exc:
        return str(exc)
    return None


def _extract_fallback_target(content: bytes) -> str | None:
    payload = _parse_json(content)
    if not isinstance(payload, dict):
        return None
    target = payload.get("fallback_target")
    return target if isinstance(target, str) else None


def _record_event(ctx: TransactionContext, outcome: str, original_content: bytes) -> None:
    event = HealEvent(
        trace_id=ctx.trace_id,
        timestamp=datetime.now(timezone.utc),
        route=ctx.route,
        route_class=ctx.route_class.value,
        outcome=outcome,
        original_payload=_parse_json(original_content),
        healed_payload=None,
        diagnosis=None,
        call_stack=list(ctx.call_stack),
        heal_count=ctx.heal_count,
        signature=None,
    )
    event_store.append(event)
    log_event(
        logger, logging.WARNING, "heal_event",
        outcome=outcome, trace_id=ctx.trace_id, route=ctx.route,
        route_class=ctx.route_class.value, heal_count=ctx.heal_count,
        call_stack=list(ctx.call_stack),
    )


def _loud_response(ctx: TransactionContext, status: int, content: bytes, headers: dict, *, synthesize: bool) -> Response:
    response_headers = dict(headers)
    if ctx.idempotency_key:
        response_headers["Idempotency-Key"] = ctx.idempotency_key

    if not synthesize:
        # The upstream failure was already loud (5xx/timeout) -- show the real thing.
        return Response(content=content, status_code=status, headers=response_headers)

    # The upstream returned 200 with a drifted body. Passing that through would be
    # exactly the silent failure this product exists to prevent, so we replace it
    # with a loud error instead of the deceptive success.
    response_headers["content-type"] = "application/json"
    body = json.dumps({
        "error": "schema_drift_unresolved",
        "trace_id": ctx.trace_id,
        "detail": "response diverged from the expected schema and could not be healed",
    }).encode()
    return Response(content=body, status_code=502, headers=response_headers, media_type="application/json")


async def handle_circuit_open(ctx: TransactionContext) -> Response:
    outcome = "budget_exhausted" if ctx.route_class == RouteClass.INFORMATIONAL else "failed_loud"
    _record_event(ctx, outcome, b"")
    headers = {"content-type": "application/json"}
    if ctx.idempotency_key:
        headers["Idempotency-Key"] = ctx.idempotency_key
    body = json.dumps({"error": "circuit_open", "trace_id": ctx.trace_id, "route": ctx.route}).encode()
    return Response(content=body, status_code=503, headers=headers, media_type="application/json")


async def handle_transactional_failure(ctx: TransactionContext, status: int, content: bytes, headers: dict) -> Response:
    """TRD 3.1: short-circuits the entire heal pipeline. No loop detector, no
    budget check, no diagnosis -- one strike trips the circuit."""
    circuit_registry.get(ctx.route).trip()
    _record_event(ctx, "failed_loud", content)
    return _loud_response(ctx, status, content, headers, synthesize=False)


async def handle_informational_failure(
    ctx: TransactionContext, status: int, content: bytes, headers: dict, *, is_transport_failure: bool,
) -> Response:
    circuit = circuit_registry.get(ctx.route)

    fallback_target = _extract_fallback_target(content)
    if fallback_target is not None and not ctx.push(fallback_target):
        _record_event(ctx, "loop_suppressed", content)
        return _loud_response(ctx, status, content, headers, synthesize=not is_transport_failure)

    if ctx.heal_count >= settings.max_heals_per_transaction or circuit.is_window_exhausted():
        circuit.trip()
        _record_event(ctx, "budget_exhausted", content)
        return _loud_response(ctx, status, content, headers, synthesize=not is_transport_failure)

    ctx.heal_count += 1
    circuit.record_heal()

    if fallback_target is not None:
        result = await dispatch_upstream(fallback_target, "GET", {}, b"", {})
        if result.ok:
            return Response(content=result.content, status_code=result.status_code, headers=result.headers)
        return await handle_informational_failure(
            ctx, result.status_code, result.content, result.headers, is_transport_failure=True,
        )

    # No fallback target to try, and Gemini diagnosis + heal executor land in
    # Phase 3. Never heal blind: fail loud rather than guess.
    _record_event(ctx, "failed_loud", content)
    return _loud_response(ctx, status, content, headers, synthesize=not is_transport_failure)

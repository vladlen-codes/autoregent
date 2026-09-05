import json
import logging
from datetime import datetime, timezone

from fastapi import Response
from pydantic import ValidationError as PydanticValidationError

from app.circuit import circuit_registry
from app.config import settings
from app.diagnosis import DriftDiagnosis
from app.dispatch import dispatch_upstream
from app.events import HealEvent, event_store
from app.gemini_diagnosis import diagnose_drift
from app.heal_executor import apply_field_mapping, validate_healed_payload
from app.logging_config import log_event
from app.route_classifier import RouteClass
from app.schema_registry import get_expected_schema
from app.signing import sign_event
from app.transaction_context import TransactionContext

logger = logging.getLogger("autoregent.heal")


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


def _record_event(
    ctx: TransactionContext,
    outcome: str,
    original_content: bytes | dict | list,
    *,
    failure_reason: str | None = None,
    is_transport_failure: bool = False,
    diagnosis: DriftDiagnosis | None = None,
    healed_payload: dict | None = None,
) -> HealEvent:
    original_payload = (
        original_content if isinstance(original_content, (dict, list)) else _parse_json(original_content)
    )
    event = HealEvent(
        trace_id=ctx.trace_id,
        timestamp=datetime.now(timezone.utc),
        route=ctx.route,
        route_class=ctx.route_class.value,
        outcome=outcome,
        failure_reason=failure_reason,
        is_transport_failure=is_transport_failure,
        original_payload=original_payload,
        healed_payload=healed_payload,
        diagnosis=diagnosis,
        call_stack=list(ctx.call_stack),
        heal_count=ctx.heal_count,
        signature=None,
    )
    event.signature = sign_event(event)
    event_store.append(event)
    log_event(
        logger, logging.WARNING, "heal_event",
        outcome=outcome, trace_id=ctx.trace_id, route=ctx.route,
        route_class=ctx.route_class.value, heal_count=ctx.heal_count,
        call_stack=list(ctx.call_stack),
    )
    return event


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
    _record_event(ctx, outcome, b"", failure_reason="circuit_open_precheck", is_transport_failure=True)
    headers = {"content-type": "application/json"}
    if ctx.idempotency_key:
        headers["Idempotency-Key"] = ctx.idempotency_key
    body = json.dumps({"error": "circuit_open", "trace_id": ctx.trace_id, "route": ctx.route}).encode()
    return Response(content=body, status_code=503, headers=headers, media_type="application/json")


async def handle_transactional_failure(ctx: TransactionContext, status: int, content: bytes, headers: dict) -> Response:
    """TRD 3.1: short-circuits the entire heal pipeline. No loop detector, no
    budget check, no diagnosis -- one strike trips the circuit."""
    circuit_registry.get(ctx.route).trip()
    _record_event(
        ctx, "failed_loud", content,
        failure_reason="transactional_short_circuit", is_transport_failure=True,
    )
    return _loud_response(ctx, status, content, headers, synthesize=False)


async def handle_informational_failure(
    ctx: TransactionContext, status: int, content: bytes, headers: dict, *, is_transport_failure: bool,
) -> Response:
    circuit = circuit_registry.get(ctx.route)

    fallback_target = _extract_fallback_target(content)
    if fallback_target is not None and not ctx.push(fallback_target):
        _record_event(
            ctx, "loop_suppressed", content,
            failure_reason="loop_detected", is_transport_failure=is_transport_failure,
        )
        return _loud_response(ctx, status, content, headers, synthesize=not is_transport_failure)

    transaction_exhausted = ctx.heal_count >= settings.max_heals_per_transaction
    if transaction_exhausted or circuit.is_window_exhausted():
        circuit.trip()
        reason = "budget_exhausted_transaction" if transaction_exhausted else "budget_exhausted_window"
        _record_event(
            ctx, "budget_exhausted", content,
            failure_reason=reason, is_transport_failure=is_transport_failure,
        )
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

    if is_transport_failure:
        # A real upstream failure (5xx/timeout) -- there's no payload shape to
        # diagnose or remap, only a genuine error to show.
        _record_event(
            ctx, "failed_loud", content,
            failure_reason="transport_failure_no_diagnosis", is_transport_failure=True,
        )
        return _loud_response(ctx, status, content, headers, synthesize=False)

    return await _attempt_ai_heal(ctx, status, content, headers)


async def _attempt_ai_heal(ctx: TransactionContext, status: int, content: bytes, headers: dict) -> Response:
    """Gemini can authorise a heal; it can never force one through. Every exit
    from an uncertain diagnosis is a loud failure."""
    schema = get_expected_schema(ctx.route)
    original_payload = _parse_json(content)

    if schema is None or not isinstance(original_payload, dict):
        _record_event(ctx, "failed_loud", content, failure_reason="no_expected_schema")
        return _loud_response(ctx, status, content, headers, synthesize=True)

    validation_error = validate_against_schema(ctx.route, content) or "response diverged from the expected schema"

    diagnosis = await diagnose_drift(ctx.route, schema.model_json_schema(), validation_error, original_payload)

    if diagnosis is None:
        _record_event(ctx, "failed_loud", original_payload, failure_reason="gemini_unavailable")
        return _loud_response(ctx, status, content, headers, synthesize=True)

    if (
        diagnosis.recommendation != "heal"
        or diagnosis.confidence < settings.gemini_confidence_threshold
        or diagnosis.drift_type == "unrecoverable"
    ):
        log_event(
            logger, logging.INFO, "heal_declined",
            route=ctx.route, recommendation=diagnosis.recommendation,
            confidence=diagnosis.confidence, drift_type=diagnosis.drift_type,
        )
        _record_event(ctx, "failed_loud", original_payload, failure_reason="gemini_declined", diagnosis=diagnosis)
        return _loud_response(ctx, status, content, headers, synthesize=True)

    healed_payload = apply_field_mapping(diagnosis.field_mapping, original_payload)
    if healed_payload is None:
        log_event(logger, logging.WARNING, "heal_executor_missing_source", route=ctx.route)
        _record_event(
            ctx, "failed_loud", original_payload,
            failure_reason="heal_executor_missing_source", diagnosis=diagnosis,
        )
        return _loud_response(ctx, status, content, headers, synthesize=True)

    gate_error = validate_healed_payload(schema, healed_payload)
    if gate_error is not None:
        log_event(logger, logging.ERROR, "validation_gate_blocked", route=ctx.route, detail=gate_error)
        _record_event(
            ctx, "failed_loud", original_payload,
            failure_reason="validation_gate_blocked", diagnosis=diagnosis,
        )
        return _loud_response(ctx, status, content, headers, synthesize=True)

    event = _record_event(ctx, "healed", original_payload, diagnosis=diagnosis, healed_payload=healed_payload)
    log_event(
        logger, logging.ERROR, "divergence_alert",
        trace_id=ctx.trace_id, route=ctx.route, drift_type=diagnosis.drift_type,
        confidence=diagnosis.confidence, signature=event.signature,
    )
    response_headers = {
        "content-type": "application/json",
        "X-Autoregent-Healed": "true",
        "X-Autoregent-Trace-Id": ctx.trace_id,
        "X-Autoregent-Drift-Type": diagnosis.drift_type,
        "X-Autoregent-Confidence": str(diagnosis.confidence),
        "X-Autoregent-Signature": event.signature,
    }
    if ctx.idempotency_key:
        response_headers["Idempotency-Key"] = ctx.idempotency_key
    return Response(
        content=json.dumps(healed_payload).encode(),
        status_code=200,
        headers=response_headers,
        media_type="application/json",
    )

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.diagnosis import DriftDiagnosis


FailureReason = Literal[
    "circuit_open_precheck",
    "transactional_short_circuit",
    "loop_detected",
    "budget_exhausted_transaction",
    "budget_exhausted_window",
    "transport_failure_no_diagnosis",
    "gemini_unavailable",
    "gemini_declined",
    "heal_executor_missing_source",
    "validation_gate_blocked",
    "no_expected_schema",
]


class HealEvent(BaseModel):
    trace_id: str
    timestamp: datetime
    route: str
    route_class: Literal["TRANSACTIONAL", "INFORMATIONAL"]
    outcome: Literal["healed", "failed_loud", "loop_suppressed", "budget_exhausted"]
    # Which exact pipeline stage this request stopped at -- None only for a
    # successful heal. Powers the dashboard's flow diagram; "failed_loud" alone
    # is ambiguous (circuit-open, transactional, Gemini decline, and a blocked
    # validation gate all report that same outcome).
    failure_reason: FailureReason | None = None
    # True if the upstream itself errored (5xx/timeout/connection failure) --
    # false means we got a 200 whose *body* didn't match the expected schema.
    # budget_exhausted can be reached via either path, so this can't be
    # inferred from failure_reason alone; the dashboard needs it explicitly
    # to know whether a "Schema Validation" step even applies.
    is_transport_failure: bool = False
    original_payload: dict | list | None = None
    healed_payload: dict | list | None = None
    diagnosis: DriftDiagnosis | None = None
    call_stack: list[str]
    heal_count: int
    signature: str | None = None


class EventStore:
    """Append-only, in-memory. Restart clears it -- acceptable for v0.1,
    called out honestly in the submission narrative."""

    def __init__(self) -> None:
        self._events: list[HealEvent] = []

    def append(self, event: HealEvent) -> None:
        self._events.append(event)

    def all(self) -> list[HealEvent]:
        return list(self._events)


event_store = EventStore()

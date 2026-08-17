from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.diagnosis import DriftDiagnosis


class HealEvent(BaseModel):
    trace_id: str
    timestamp: datetime
    route: str
    route_class: Literal["TRANSACTIONAL", "INFORMATIONAL"]
    outcome: Literal["healed", "failed_loud", "loop_suppressed", "budget_exhausted"]
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

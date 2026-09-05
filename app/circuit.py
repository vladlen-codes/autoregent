import time
from collections import deque
from enum import StrEnum

from app.config import settings


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class RouteCircuit:
    """One circuit per gateway route, guarding the heal budget for that route.

    CLOSED -> OPEN on budget exhaustion or a detected loop.
    OPEN -> HALF_OPEN after the cooldown elapses; the next request through is
    the probe.
    HALF_OPEN -> CLOSED on probe success, back to OPEN on probe failure.
    """

    def __init__(self) -> None:
        self.state = CircuitState.CLOSED
        self.opened_at: float | None = None
        self._heal_timestamps: deque[float] = deque()

    def _prune(self, now: float) -> None:
        window = settings.rolling_window_seconds
        while self._heal_timestamps and now - self._heal_timestamps[0] > window:
            self._heal_timestamps.popleft()

    def record_heal(self) -> None:
        self._heal_timestamps.append(time.monotonic())

    def is_window_exhausted(self) -> bool:
        now = time.monotonic()
        self._prune(now)
        return len(self._heal_timestamps) >= settings.rolling_window_max_heals

    def heals_in_window(self) -> int:
        self._prune(time.monotonic())
        return len(self._heal_timestamps)

    def trip(self) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = time.monotonic()

    def allow_request(self) -> bool:
        if self.state != CircuitState.OPEN:
            return True
        assert self.opened_at is not None
        if time.monotonic() - self.opened_at >= settings.circuit_cooldown_seconds:
            self.state = CircuitState.HALF_OPEN
            return True
        return False

    def record_probe_result(self, success: bool) -> None:
        if self.state != CircuitState.HALF_OPEN:
            return
        if success:
            self.state = CircuitState.CLOSED
            self.opened_at = None
            self._heal_timestamps.clear()
        else:
            self.trip()


class CircuitRegistry:
    def __init__(self) -> None:
        self._circuits: dict[str, RouteCircuit] = {}

    def get(self, route: str) -> RouteCircuit:
        if route not in self._circuits:
            self._circuits[route] = RouteCircuit()
        return self._circuits[route]

    def snapshot(self) -> dict[str, dict]:
        return {
            route: {"state": circuit.state.value, "heals_in_window": circuit.heals_in_window()}
            for route, circuit in self._circuits.items()
        }


circuit_registry = CircuitRegistry()

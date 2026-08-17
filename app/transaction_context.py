import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.route_classifier import RouteClass


@dataclass
class TransactionContext:
    route: str
    route_class: RouteClass
    idempotency_key: str | None = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    call_stack: list[str] = field(default_factory=list)
    heal_count: int = 0
    suppress_retries: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def push(self, target: str) -> bool:
        """Append a dispatch target to the call stack.

        Returns False if the target is already present -- the transaction is
        cycling back onto something it already tried, which is the loop
        detector's signal to abandon healing and fail loudly.
        """
        if target in self.call_stack:
            self.suppress_retries = True
            return False
        self.call_stack.append(target)
        return True

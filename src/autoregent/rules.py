import fnmatch
from enum import StrEnum

from pydantic import BaseModel


class RouteClass(StrEnum):
    TRANSACTIONAL = "TRANSACTIONAL"
    INFORMATIONAL = "INFORMATIONAL"


class RouteRules:
    """Everything a self-hoster configures about their own routes: which paths
    are write-adjacent (never healed, ever) and which informational paths have
    a known expected schema (eligible for AI-diagnosed healing).

    Classification happens once at ingress and is immutable for the request
    lifetime -- and it happens BEFORE any heal logic runs, so a transactional
    route is structurally excluded from the AI pipeline, not policy-excluded.

        rules = (
            RouteRules()
            .transactional("*/transfer/*", "*/charge/*", "*ledger*")
            .expect("accounts/*", AccountBalance)
            .expect("profile/*", UserProfile)
        )

    First match wins in both lists; an unmatched path defaults to
    INFORMATIONAL for classification, and to "no expected schema" (so no
    healing is attempted -- an unknown shape is never diagnosed) for schemas.
    """

    def __init__(self) -> None:
        self._transactional_patterns: list[str] = []
        self._schema_patterns: list[tuple[str, type[BaseModel]]] = []

    def transactional(self, *patterns: str) -> "RouteRules":
        """Register one or more glob patterns (matched with fnmatch against the
        proxied path) as write-adjacent routes that must never be healed."""
        self._transactional_patterns.extend(patterns)
        return self

    def expect(self, pattern: str, schema: type[BaseModel]) -> "RouteRules":
        """Register the Pydantic model an informational route's response body
        is expected to satisfy. Required for that route to be eligible for
        AI-diagnosed healing at all -- an unregistered path is never healed,
        it just fails loud like any other unrecognised failure."""
        self._schema_patterns.append((pattern, schema))
        return self

    def classify(self, path: str) -> RouteClass:
        for pattern in self._transactional_patterns:
            if fnmatch.fnmatch(path, pattern):
                return RouteClass.TRANSACTIONAL
        return RouteClass.INFORMATIONAL

    def schema_for(self, path: str) -> type[BaseModel] | None:
        for pattern, model in self._schema_patterns:
            if fnmatch.fnmatch(path, pattern):
                return model
        return None

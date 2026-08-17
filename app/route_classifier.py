import fnmatch
from enum import StrEnum


class RouteClass(StrEnum):
    TRANSACTIONAL = "TRANSACTIONAL"
    INFORMATIONAL = "INFORMATIONAL"


# Static config: matched against the proxied path (e.g. "mock/field_rename").
# First match wins; anything unmatched defaults to INFORMATIONAL. Classification
# happens once at ingress and is immutable for the request lifetime.
TRANSACTIONAL_PATTERNS = [
    "*txn/*",
    "*transfer*",
    "*charge*",
    "*payment*",
    "*ledger*",
]


def classify_route(path: str) -> RouteClass:
    for pattern in TRANSACTIONAL_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return RouteClass.TRANSACTIONAL
    return RouteClass.INFORMATIONAL

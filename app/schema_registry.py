import fnmatch

from pydantic import BaseModel

from app.models import AccountBalance

# Path patterns -> the Pydantic model an INFORMATIONAL route's response body
# must satisfy. No entry means no validation is attempted (schema unknown).
EXPECTED_SCHEMA_PATTERNS: list[tuple[str, type[BaseModel]]] = [
    ("mock/*", AccountBalance),
]


def get_expected_schema(path: str) -> type[BaseModel] | None:
    for pattern, model in EXPECTED_SCHEMA_PATTERNS:
        if fnmatch.fnmatch(path, pattern):
            return model
    return None

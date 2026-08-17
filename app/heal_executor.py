import json

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError


def apply_field_mapping(field_mapping: dict[str, str], original_payload: dict) -> dict | None:
    """Pure transformation: for each expected field, pull its value from the
    source key Gemini named in field_mapping. No value is generated, invented,
    or defaulted. Returns None if any mapped source key is absent -- the heal
    fails rather than guessing."""
    healed: dict = {}
    for expected_field, source_key in field_mapping.items():
        if source_key not in original_payload:
            return None
        healed[expected_field] = original_payload[source_key]
    return healed


def validate_healed_payload(schema: type[BaseModel], healed_payload: dict) -> str | None:
    """The egress block: deterministic, no AI. Returns a description of the
    failure, or None if the healed payload satisfies the expected schema."""
    try:
        schema.model_validate_json(json.dumps(healed_payload), strict=True)
    except PydanticValidationError as exc:
        return str(exc)
    return None

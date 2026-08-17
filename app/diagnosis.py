from typing import Literal

from pydantic import BaseModel


class DriftDiagnosis(BaseModel):
    """Gemini's structured output. Wired in Phase 3 -- defined now so the
    HealEvent audit record shape doesn't change once it lands."""

    drift_type: Literal["field_rename", "type_change", "nesting_change", "missing_field", "unrecoverable"]
    recommendation: Literal["heal", "fail_loud"]
    confidence: float
    field_mapping: dict[str, str]
    reasoning: str

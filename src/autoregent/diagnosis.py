from typing import Literal

from pydantic import BaseModel


class DriftDiagnosis(BaseModel):
    """Gemini's structured output -- the diagnosis it authorises, never forces."""

    drift_type: Literal["field_rename", "type_change", "nesting_change", "missing_field", "unrecoverable"]
    recommendation: Literal["heal", "fail_loud"]
    confidence: float
    field_mapping: dict[str, str]
    reasoning: str

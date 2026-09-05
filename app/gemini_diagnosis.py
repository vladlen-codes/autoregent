import asyncio
import json
import logging
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.config import settings
from app.diagnosis import DriftDiagnosis
from app.logging_config import log_event

logger = logging.getLogger("autoregent.gemini")

_client: genai.Client | None = None


class _FieldMappingEntry(BaseModel):
    expected_field: str
    source_field: str


class _GeminiDriftResponse(BaseModel):
    """Wire format for the Gemini call. field_mapping is a list of pairs, not
    a dict[str, str] -- the Developer API's structured-output mode rejects
    schemas with `additionalProperties` (open-ended dict/map types), which is
    exactly what Pydantic generates for a dict field. Vertex AI Enterprise
    mode supports it; the plain AI Studio key used here does not. Converted
    back into DriftDiagnosis.field_mapping (a real dict) after parsing."""

    drift_type: Literal["field_rename", "type_change", "nesting_change", "missing_field", "unrecoverable"]
    recommendation: Literal["heal", "fail_loud"]
    confidence: float
    field_mapping: list[_FieldMappingEntry]
    reasoning: str

    def to_diagnosis(self) -> DriftDiagnosis:
        return DriftDiagnosis(
            drift_type=self.drift_type,
            recommendation=self.recommendation,
            confidence=self.confidence,
            field_mapping={e.expected_field: e.source_field for e in self.field_mapping},
            reasoning=self.reasoning,
        )


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _build_prompt(route: str, expected_schema: dict, validation_error: str, original_payload: dict) -> str:
    return (
        "An API gateway received a response that failed validation against its expected schema. "
        "Diagnose the drift and decide whether it is safely healable by pure field remapping -- "
        "never by inventing or defaulting a value.\n\n"
        f"Route: {route}\n\n"
        f"Expected JSON schema:\n{json.dumps(expected_schema, indent=2)}\n\n"
        f"Actual response payload:\n{json.dumps(original_payload, indent=2)}\n\n"
        f"Pydantic validation error:\n{validation_error}\n\n"
        "field_mapping must have one entry per field in the expected schema: expected_field is "
        "exactly that field's name, source_field is the exact key in the actual payload where its "
        "value can be found. Include an entry only if the value genuinely exists in the actual "
        "payload. If any required field has no source, or the drift cannot be resolved by pure "
        'remapping, set drift_type to "unrecoverable" and recommendation to "fail_loud".'
    )


async def diagnose_drift(
    route: str, expected_schema: dict, validation_error: str, original_payload: dict,
) -> DriftDiagnosis | None:
    """Returns a validated DriftDiagnosis, or None if the call timed out, errored, or
    returned something that doesn't parse. Every None means: fail loud, never heal blind."""
    if not settings.gemini_api_key:
        log_event(logger, logging.WARNING, "gemini_skipped", reason="no_api_key", route=route)
        return None

    prompt = _build_prompt(route, expected_schema, validation_error, original_payload)
    log_event(logger, logging.INFO, "gemini_request", route=route, prompt=prompt)

    try:
        response = await asyncio.wait_for(
            _get_client().aio.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_GeminiDriftResponse,
                ),
            ),
            timeout=settings.gemini_timeout_seconds,
        )
    except TimeoutError:
        log_event(logger, logging.WARNING, "gemini_timeout", route=route, timeout_seconds=settings.gemini_timeout_seconds)
        return None
    except Exception as exc:
        log_event(logger, logging.ERROR, "gemini_error", route=route, error=str(exc))
        return None

    raw_text = response.text
    log_event(logger, logging.INFO, "gemini_response", route=route, raw=raw_text)

    if raw_text is None:
        log_event(logger, logging.ERROR, "gemini_malformed_response", route=route, error="empty response")
        return None

    try:
        return _GeminiDriftResponse.model_validate_json(raw_text).to_diagnosis()
    except PydanticValidationError as exc:
        log_event(logger, logging.ERROR, "gemini_malformed_response", route=route, error=str(exc))
        return None

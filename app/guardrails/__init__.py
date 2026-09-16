"""
Unified application guardrails package.

Provides perimeter guards for API requests, prompt/SQL injection scanning,
PII redaction via Microsoft Presidio, output validation, and guardrail middleware.
"""

from app.guardrails.input_validator import (
    validate_input,
    InputValidationError,
)
from app.guardrails.injection_scanner import (
    scan_fields,
    scan_text,
    assert_no_injection,
    check_prompt_guard,
    InjectionDetectedError,
)
from app.guardrails.pii_redactor import (
    redact_for_logging,
    redact_for_response,
    redact_text,
    redact_dict,
    redact_value,
)
from app.guardrails.output_validator import (
    validate_investigation_result,
    validate_no_discrepancy_result,
    OutputValidationError,
)
from app.guardrails.middleware import InputGuardrailMiddleware

__all__ = [
    "validate_input",
    "InputValidationError",
    "scan_fields",
    "scan_text",
    "assert_no_injection",
    "check_prompt_guard",
    "InjectionDetectedError",
    "redact_for_logging",
    "redact_for_response",
    "redact_text",
    "redact_dict",
    "redact_value",
    "validate_investigation_result",
    "validate_no_discrepancy_result",
    "OutputValidationError",
    "InputGuardrailMiddleware",
]


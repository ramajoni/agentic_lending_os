"""
Guard 1 — Input/schema validation.

Validates incoming loan application payloads using Pydantic.
Rejects malformed payloads before anything runs.
"""

from pydantic import ValidationError
from app.models.api_schemas import VerificationRequest
from app.config.logger import get_logger

log = get_logger(__name__)


class InputValidationError(Exception):
    """Raised when the input payload fails schema validation."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"Input validation failed: {len(errors)} error(s)")


def validate_input(payload: dict) -> VerificationRequest:
    """Validate raw request payload against the VerificationRequest schema.

    Args:
        payload: Raw JSON body from the POST request.

    Returns:
        A validated VerificationRequest instance.

    Raises:
        InputValidationError: If the payload fails validation.
    """
    try:
        request = VerificationRequest.model_validate(payload)
        log.info(
            "Guard 1 PASSED — input validation OK for applicant_id=%s",
            request.application.applicant_id,
        )
        return request
    except ValidationError as e:
        errors = e.errors()
        log.warning("Guard 1 BLOCKED — input validation failed: %s", errors)
        raise InputValidationError(errors) from e

"""
Guard 8 — Output schema validation.

Validates the final investigation result against the output schema
before the response leaves the system.
"""

from pydantic import ValidationError
from app.models.investigation import InvestigationResult, NoDiscrepancyResult
from app.config.logger import get_logger

log = get_logger(__name__)


class OutputValidationError(Exception):
    """Raised when the output fails schema validation."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"Output validation failed: {len(errors)} error(s)")


def validate_investigation_result(data: dict) -> InvestigationResult:
    """Validate investigation result against the output schema.

    Args:
        data: Dictionary representation of the investigation result.

    Returns:
        A validated InvestigationResult instance.

    Raises:
        OutputValidationError: If the result fails schema validation.
    """
    try:
        result = InvestigationResult.model_validate(data)
        log.info(
            "Guard 8 PASSED — output validation OK (decision=%s, confidence=%s)",
            result.decision.value,
            result.confidence,
        )
        return result
    except ValidationError as e:
        errors = e.errors()
        log.warning("Guard 8 BLOCKED — output validation failed: %s", errors)
        raise OutputValidationError(errors) from e


def validate_no_discrepancy_result(data: dict) -> NoDiscrepancyResult:
    """Validate a no-discrepancy result."""
    try:
        result = NoDiscrepancyResult.model_validate(data)
        log.info("Guard 8 PASSED — no-discrepancy output validation OK")
        return result
    except ValidationError as e:
        errors = e.errors()
        log.warning("Guard 8 BLOCKED — output validation failed: %s", errors)
        raise OutputValidationError(errors) from e

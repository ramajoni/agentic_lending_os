"""
API request/response schemas.

These are the public-facing Pydantic models used by Guards 1 and 8.
"""

from pydantic import BaseModel, Field
from app.models.applicant import LoanApplication
from app.models.investigation import InvestigationResult, NoDiscrepancyResult


# ── Request schemas (Guard 1: input validation) ─────────────────────────────

class VerificationRequest(BaseModel):
    """POST /api/v1/verify request body.

    Wraps a LoanApplication — Guard 1 validates this schema on entry.
    """

    application: LoanApplication


# ── Response schemas (Guard 8: output validation) ───────────────────────────

class VerificationResponse(BaseModel):
    """Successful response from the verification pipeline."""

    status: str = Field(
        default="completed",
        description="Overall status: completed | pending_approval | error",
    )
    result: InvestigationResult | NoDiscrepancyResult


class ErrorResponse(BaseModel):
    """Structured error response."""

    status: str = "error"
    error_code: str
    error_message: str
    details: dict = Field(default_factory=dict)


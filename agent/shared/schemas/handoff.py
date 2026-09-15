"""
Cross-agent handoff schemas.

Narrow, stable contracts for passing data between agents (e.g., verification -> scoring)
without exposing raw internal agent state.
"""

from typing import Literal
from pydantic import BaseModel, Field
from app.models.discrepancy import Discrepancy


class VerificationResult(BaseModel):
    """Stable handoff object containing verification output for downstream agents."""

    applicant_id: str
    decision: Literal[
        "auto_cleared",
        "escalated_to_human",
        "additional_document_requested",
        "pending_human_approval",
        "max_iterations_reached",
    ]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    requires_human_approval: bool = False

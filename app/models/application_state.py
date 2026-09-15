"""
Application state machine and role-based request/response models.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.models.applicant import LoanApplication
from app.models.discrepancy import Discrepancy


class UserType(str, Enum):
    """User roles interacting with the lending platform."""

    CUSTOMER = "customer"
    L1_REVIEWER = "l1_reviewer"
    L2_REVIEWER = "l2_reviewer"
    MANAGER = "manager"
    SYSTEM = "system"


class ApplicationState(str, Enum):
    """Lifecycle states of a loan application."""

    SUBMITTED = "submitted"
    PENDING_L1_REVIEW = "pending_l1_review"
    L2_REVIEW = "l2_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class L1Decision(str, Enum):
    """Available decisions for L1 Reviewer."""

    APPROVED = "approved"
    L2_REVIEW = "l2_review"
    REJECTED = "rejected"


class L2Decision(str, Enum):
    """Available decisions for L2 Senior Reviewer."""

    APPROVED = "approved"
    REJECTED = "rejected"


# ── Customer Models ──────────────────────────────────────────────────────────

class CustomerApplyRequest(BaseModel):
    """Customer application submission body."""

    application: LoanApplication


class CustomerApplicationResponse(BaseModel):
    """Customer-safe acknowledgment response."""

    application_id: str
    status: ApplicationState
    message: str
    submitted_at: str


class CustomerStatusResponse(BaseModel):
    """Customer-safe application status query response."""

    application_id: str
    status: ApplicationState
    submitted_at: str
    updated_at: str
    message: str


# ── Reviewer Models ──────────────────────────────────────────────────────────

class L1ReviewDecisionRequest(BaseModel):
    """L1 reviewer decision payload."""

    reviewer_id: str = Field(..., description="Unique ID of the L1 reviewer")
    decision: L1Decision = Field(..., description="Decision: approved | l2_review | rejected")
    notes: str = Field(..., min_length=3, description="Notes justifying the decision based on facts")


class L2ReviewDecisionRequest(BaseModel):
    """L2 senior reviewer decision payload with mandatory justification."""

    reviewer_id: str = Field(..., description="Unique ID of the L2 senior reviewer")
    decision: L2Decision = Field(..., description="Decision: approved | rejected")
    justification: str = Field(..., min_length=10, description="Mandatory detailed justification for final approval/rejection")


class ReviewDecisionResponse(BaseModel):
    """Confirmation of a reviewer's decision."""

    application_id: str
    previous_state: ApplicationState
    current_state: ApplicationState
    decision: str
    reviewer_id: str
    notes_or_justification: str
    timestamp: str


class QueueItemSummary(BaseModel):
    """Queue list item for L1 and L2 review queues."""

    applicant_id: str
    applicant_name: str
    current_state: ApplicationState
    has_discrepancies: bool
    discrepancy_count: int
    agent_recommendation: Optional[str] = None
    agent_confidence: Optional[float] = None
    created_at: str


class CaseDossierResponse(BaseModel):
    """Comprehensive factual dossier reviewed by L1/L2 underwriters."""

    applicant_id: str
    applicant_name: str
    current_state: ApplicationState
    created_at: str
    updated_at: str
    declared_data: dict
    dag_facts: Optional[dict] = None
    agent_findings: Optional[dict] = None
    audit_history: list[dict] = Field(default_factory=list)


# ── Manager Models ───────────────────────────────────────────────────────────

class ReviewerPerformance(BaseModel):
    """Productivity metrics for an individual reviewer."""

    reviewer_id: str
    role: str
    total_reviews: int
    approvals: int
    rejections: int
    escalations: int


class LeaderboardResponse(BaseModel):
    """Overview analytics and reviewer performance leaderboard."""

    total_applications: int
    state_distribution: dict[str, int]
    pipeline_metrics: dict[str, Any]
    reviewer_leaderboard: list[ReviewerPerformance]


class DrillDownStep(BaseModel):
    """A single chronological step in a case's lifecycle."""

    step_number: int
    stage: str
    title: str
    timestamp: str
    actor: str
    details: dict[str, Any]


class CaseDrillDownResponse(BaseModel):
    """Complete chronological audit drill-down for management."""

    applicant_id: str
    applicant_name: str
    current_state: ApplicationState
    created_at: str
    updated_at: str
    total_steps: int
    steps: list[DrillDownStep]
    raw_audit_records: list[dict]


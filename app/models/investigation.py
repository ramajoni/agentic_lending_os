"""
Investigation state and result models.

InvestigationState is the LangGraph TypedDict state that flows through
the agent graph. InvestigationResult is the final structured output.
"""

from enum import Enum
from typing import TypedDict, Literal
from pydantic import BaseModel, Field

from app.models.discrepancy import Discrepancy
from app.models.tool_call import ToolCallRecord


# ── LangGraph state (TypedDict, not Pydantic — required by LangGraph) ───────

class InvestigationState(TypedDict):
    """State that flows through the LangGraph investigation graph."""

    applicant_id: str
    agent_id: str                       # e.g. 'discrepancy_investigation_agent'
    discrepancies: list[dict]           # list of Discrepancy.model_dump()
    tool_call_history: list[dict]       # list of ToolCallRecord.model_dump()
    iteration_count: int
    max_iterations: int
    confidence: float | None
    terminal_action: str | None         # one of the terminal tool names, or None
    rationale: str | None               # human-readable explanation
    current_tool_request: dict | None   # the tool the agent wants to call next
    guardrail_violations: list[str]     # log of any guardrail blocks
    requires_human_approval: bool       # set True when terminal action chosen


# ── Final output (Pydantic — validated by Guard 8) ──────────────────────────

class InvestigationDecision(str, Enum):
    """Possible final decisions from the investigation."""

    AUTO_CLEARED = "auto_cleared"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    ADDITIONAL_DOCUMENT_REQUESTED = "additional_document_requested"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"



class InvestigationResult(BaseModel):
    """Final result of the investigation — the API response payload."""

    applicant_id: str
    decision: InvestigationDecision
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in the decision (0-1)",
    )
    rationale: str = Field(..., description="Human-readable explanation of the decision")
    discrepancies_found: list[Discrepancy] = Field(default_factory=list)
    tool_call_trace: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Full audit trail of tool calls made during investigation",
    )
    requires_human_approval: bool = Field(
        default=False,
        description="If True, a human must review and approve this decision",
    )
    guardrail_violations: list[str] = Field(
        default_factory=list,
        description="Any guardrail violations encountered during investigation",
    )


class NoDiscrepancyResult(BaseModel):
    """Result when the DAG finds no discrepancies — no agent needed."""

    applicant_id: str
    decision: str = "all_checks_passed"
    confidence: float = 1.0
    rationale: str = "All document fields match verification sources within tolerance."
    discrepancies_found: list = Field(default_factory=list)
    tool_call_trace: list = Field(default_factory=list)
    requires_human_approval: bool = False

"""
Verification agent state definition.
"""

from typing import TypedDict


class InvestigationState(TypedDict):
    """State that flows through the LangGraph verification agent graph."""

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

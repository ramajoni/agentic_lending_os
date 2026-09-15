"""
Response formatter — formats investigation results for API output.

Applies Guard 3 (PII redaction) and Guard 8 (output validation)
before the response leaves the system.
"""

from app.models.investigation import (
    InvestigationResult,
    InvestigationDecision,
    NoDiscrepancyResult,
)
from app.models.discrepancy import Discrepancy
from app.models.tool_call import ToolCallRecord
from app.models.api_schemas import VerificationResponse
from app.shared.guardrails.pii_redactor import redact_for_response
from app.api.guardrails.output_validator import validate_investigation_result, validate_no_discrepancy_result
from app.config.logger import get_logger

log = get_logger(__name__)


def format_investigation_response(final_state: dict) -> dict:
    """Format the final investigation state into a validated API response.

    Applies Guard 3 (PII redaction) and Guard 8 (output validation).

    Args:
        final_state: The final InvestigationState dict from the graph.

    Returns:
        Validated and redacted response dict.
    """
    terminal = final_state.get("terminal_action")
    requires_approval = final_state.get("requires_human_approval", False)

    # Map terminal action to decision
    if requires_approval:
        decision = InvestigationDecision.PENDING_HUMAN_APPROVAL
    elif terminal == "auto_clear":
        decision = InvestigationDecision.AUTO_CLEARED
    elif terminal == "escalate_to_human":
        decision = InvestigationDecision.ESCALATED_TO_HUMAN
    elif terminal == "request_additional_document":
        decision = InvestigationDecision.ADDITIONAL_DOCUMENT_REQUESTED
    else:
        decision = InvestigationDecision.MAX_ITERATIONS_REACHED

    # Build the result
    result_data = {
        "applicant_id": final_state.get("applicant_id", ""),
        "decision": decision.value,
        "confidence": final_state.get("confidence"),
        "rationale": final_state.get("rationale", "No rationale provided"),
        "discrepancies_found": final_state.get("discrepancies", []),
        "tool_call_trace": final_state.get("tool_call_history", []),
        "requires_human_approval": requires_approval,
        "guardrail_violations": final_state.get("guardrail_violations", []),
    }

    # Guard 8: validate output schema
    validated = validate_investigation_result(result_data)

    # Guard 3: redact PII from response
    response_dict = validated.model_dump()
    redacted = redact_for_response(response_dict)

    # Determine status
    status = "pending_approval" if requires_approval else "completed"

    return {
        "status": status,
        "result": redacted,
    }


def format_no_discrepancy_response(applicant_id: str) -> dict:
    """Format response when DAG finds no discrepancies.

    Args:
        applicant_id: The applicant ID.

    Returns:
        Validated response dict.
    """
    result_data = {
        "applicant_id": applicant_id,
        "decision": "all_checks_passed",
        "confidence": 1.0,
        "rationale": "All document fields match verification sources within tolerance.",
        "discrepancies_found": [],
        "tool_call_trace": [],
        "requires_human_approval": False,
    }

    validated = validate_no_discrepancy_result(result_data)

    return {
        "status": "completed",
        "result": validated.model_dump(),
    }

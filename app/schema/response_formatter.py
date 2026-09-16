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
from app.schema.api_schemas import VerificationResponse
from app.guardrails.pii_redactor import redact_for_response
from app.guardrails.output_validator import validate_investigation_result, validate_no_discrepancy_result
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

    # Guard 8: Validate the output structure before sending
    validated_result = validate_investigation_result(result_data)

    # Build full response
    response_data = {
        "status": "pending_approval" if requires_approval else "completed",
        "result": validated_result.model_dump(),
    }

    # Guard 3: Redact PII in response fields
    redacted_response = redact_for_response(response_data)
    log.info("Response formatted and redacted for applicant %s", final_state.get("applicant_id"))

    return redacted_response


def format_no_discrepancy_response(
    applicant_id: str,
    extracted_data: dict,
    verification_results: dict,
) -> dict:
    """Format a successful verification response when DAG found no discrepancies.

    Applies Guard 3 (PII redaction) and Guard 8 (output validation).
    """
    result_data = {
        "applicant_id": applicant_id,
        "decision": "auto_cleared",
        "rationale": "All document verifications passed with zero discrepancies. Deterministic pipeline cleared.",
        "extracted_data": extracted_data,
        "verification_results": verification_results,
    }

    # Guard 8: Validate output structure
    validated_result = validate_no_discrepancy_result(result_data)

    response_data = {
        "status": "completed",
        "result": validated_result.model_dump(),
    }

    # Guard 3: Redact PII
    redacted_response = redact_for_response(response_data)
    log.info("No-discrepancy response formatted and redacted for applicant %s", applicant_id)

    return redacted_response


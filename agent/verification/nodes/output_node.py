"""
Output node for verification agent graph.
Formats the final investigation result.
"""

from agent.verification.state import InvestigationState
from app.models.investigation import InvestigationDecision
from app.config.logger import get_logger

log = get_logger(__name__)


def output_node(state: InvestigationState) -> dict:
    """Format the final investigation result."""
    terminal = state.get("terminal_action")
    requires_approval = state.get("requires_human_approval", False)

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

    log.info(
        "═══ AGENT OUTPUT — applicant %s — decision: %s (confidence: %s) ═══",
        state.get("applicant_id"),
        decision.value,
        state.get("confidence"),
    )

    return {
        "terminal_action": terminal,
    }


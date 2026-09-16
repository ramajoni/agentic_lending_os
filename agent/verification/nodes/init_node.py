"""
Init node for verification agent graph.
Loads discrepancies from DAG output into state.
"""

from agent.verification.state import InvestigationState
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def init_node(state: InvestigationState) -> dict:
    """Load discrepancies from DAG output into state."""
    agent_id = state.get("agent_id", "discrepancy_investigation_agent")
    log.info(
        "═══ AGENT INIT — applicant %s (%s), %d discrepancies ═══",
        state["applicant_id"],
        agent_id,
        len(state["discrepancies"]),
    )
    return {
        "agent_id": agent_id,
        "iteration_count": 0,
        "max_iterations": agent_config.max_iterations,
        "confidence": None,
        "terminal_action": None,
        "rationale": None,
        "current_tool_request": None,
        "guardrail_violations": [],
        "requires_human_approval": False,
    }


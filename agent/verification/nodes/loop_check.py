"""
Loop check and loop routing for verification agent graph.
Increments iteration count and enforces safety caps.
"""

from agent.verification.state import InvestigationState
from agent.verification.guardrails.confidence_router import evaluate_confidence
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def loop_check(state: InvestigationState) -> dict:
    """Increment iteration count and enforce safety cap."""
    new_count = state.get("iteration_count", 0) + 1
    max_iter = state.get("max_iterations", agent_config.max_iterations)

    log.info("Loop check — iteration %d/%d", new_count, max_iter)
    updates = {"iteration_count": new_count}

    if state.get("terminal_action"):
        routing = evaluate_confidence(
            state.get("confidence"),
            new_count,
            max_iter,
        )
        log.info("Confidence routing: %s (terminal action: %s)", routing, state["terminal_action"])
    elif new_count >= max_iter:
        log.warning("Max iterations reached — forcing escalation")
        updates["terminal_action"] = "escalate_to_human"
        updates["rationale"] = (
            f"Max iterations ({max_iter}) reached without resolution. "
            f"Last confidence: {state.get('confidence')}. Escalating for human review."
        )

    return updates


def route_after_loop_check(state: InvestigationState) -> str:
    """Determine the next node after loop_check."""
    if state.get("terminal_action"):
        return "critical_action_gate"
    return "reasoning"


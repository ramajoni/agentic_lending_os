"""
Reasoning node for verification agent graph.
Uses LLM reasoning to decide next tool or terminal action.
"""

from agent.verification.state import InvestigationState
from agent.verification.reasoning import invoke_reasoning
from app.config.logger import get_logger

log = get_logger(__name__)


def reasoning_node(state: InvestigationState) -> dict:
    """LLM reasoning — decides next tool or terminal action."""
    decision = invoke_reasoning(state)
    log.info(
        "Reasoning → action='%s', confidence=%s, rationale='%s'",
        decision["action"],
        decision.get("confidence"),
        decision.get("rationale", "")[:100],
    )
    return {
        "current_tool_request": decision,
        "confidence": decision.get("confidence"),
        "rationale": decision.get("rationale"),
    }


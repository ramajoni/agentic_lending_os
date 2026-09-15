"""
Guard 10 — Critical-action approval gate (non-blocking).

When the agent reaches a terminal action (auto_clear, escalate_to_human,
request_additional_document), this gate marks the case as requiring
human approval and returns immediately — freeing agent resources.

The actual approval happens asynchronously outside the agent loop.
"""

from app.config.logger import get_logger
from agent.verification.guardrails.tool_allowlist import TERMINAL_TOOLS

log = get_logger(__name__)


def check_requires_approval(terminal_action: str | None) -> bool:
    """Check if the chosen terminal action requires human approval.

    Args:
        terminal_action: The terminal tool selected by the agent.

    Returns:
        True if human approval is required, False otherwise.
    """
    if terminal_action is None:
        return False

    if terminal_action not in TERMINAL_TOOLS:
        log.warning(
            "Guard 10 — unexpected terminal action '%s' (not in TERMINAL_TOOLS)",
            terminal_action,
        )
        return True  # err on the side of caution

    # All terminal actions require human approval in this POC
    log.info(
        "Guard 10 — terminal action '%s' requires human approval. "
        "Marking case and releasing resources.",
        terminal_action,
    )
    return True


def apply_approval_gate(state: dict) -> dict:
    """Apply the critical-action gate to the investigation state.

    This does NOT block. It marks the state as requiring approval
    and returns immediately so the agent can release resources.

    Args:
        state: Current InvestigationState dict.

    Returns:
        Updated state with requires_human_approval set.
    """
    terminal_action = state.get("terminal_action")

    if check_requires_approval(terminal_action):
        state["requires_human_approval"] = True
        log.info(
            "Guard 10 APPLIED — case marked as pending_human_approval "
            "(action=%s, applicant=%s)",
            terminal_action,
            state.get("applicant_id", "unknown"),
        )
    else:
        state["requires_human_approval"] = False

    return state

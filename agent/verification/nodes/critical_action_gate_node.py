"""
Critical action gate node for verification agent graph.
Guard 10 — non-blocking approval gate for terminal actions.
"""

from agent.verification.state import InvestigationState
from agent.verification.guardrails.critical_action_gate import apply_approval_gate


def critical_action_gate_node(state: InvestigationState) -> dict:
    """Guard 10 — non-blocking approval gate for terminal actions."""
    updated = apply_approval_gate(dict(state))
    return {
        "requires_human_approval": updated.get("requires_human_approval", True),
    }


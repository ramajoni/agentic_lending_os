"""
Allowlist gate node for verification agent graph.
Guard 4 — validate the proposed tool call against the allowlist.
"""

from agent.verification.state import InvestigationState
from agent.verification.guardrails.tool_allowlist import validate_tool_call
from app.config.logger import get_logger

log = get_logger(__name__)


def allowlist_gate(state: InvestigationState) -> dict:
    """Guard 4 — validate the proposed tool call against the allowlist."""
    request = state.get("current_tool_request", {})
    tool_name = request.get("action", "")
    agent_id = state.get("agent_id", "discrepancy_investigation_agent")
    arguments = request.get("arguments", {})

    is_allowed, reason = validate_tool_call(
        tool_name=tool_name,
        tool_call_history=state.get("tool_call_history", []),
        state=state,
        agent_id=agent_id,
        arguments=arguments,
    )

    if not is_allowed:
        log.warning("Allowlist gate BLOCKED tool '%s': %s", tool_name, reason)
        violations = list(state.get("guardrail_violations", []))
        violations.append(f"Guard 4: {reason}")

        return {
            "guardrail_violations": violations,
            "current_tool_request": {
                "action": "escalate_to_human",
                "arguments": {
                    "reason": f"Original tool '{tool_name}' was blocked by allowlist: {reason}",
                    "priority": "high",
                },
                "rationale": f"Allowlist gate blocked '{tool_name}': {reason}. Escalating.",
                "confidence": state.get("confidence"),
            },
        }

    return {}


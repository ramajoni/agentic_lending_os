"""
Demonstration: Guard 4 duplicate tool call enforcement.

Tests two scenarios:
1. Non-terminal tool called with identical arguments twice (e.g. reverify_alternate_source).
2. Terminal tool called twice (e.g. escalate_to_human or auto_clear).
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from agent.verification.guardrails.tool_allowlist import validate_tool_call
from agent.verification.nodes import allowlist_gate
from agent.verification.state import InvestigationState

print("=" * 70)
print("TEST 1: Agent attempts to call non-terminal tool twice with identical args")
print("=" * 70)

# Simulating state after tool 'reverify_alternate_source' was executed once
history = [
    {
        "call": {
            "tool_name": "reverify_alternate_source",
            "arguments": {"field_name": "applicant_name", "applicant_id": "APP-TEST-001"},
            "rationale": "Checking Aadhaar alternate source for name variation",
        },
        "result": {
            "tool_name": "reverify_alternate_source",
            "success": True,
            "result": {"alternate_verified_value": "Rajesh Kumar Sharma"},
        },
    }
]

state: InvestigationState = {
    "applicant_id": "APP-TEST-001",
    "agent_id": "discrepancy_investigation_agent",
    "discrepancies": [{"type": "name_mismatch", "severity": "low"}],
    "tool_call_history": history,
    "iteration_count": 1,
    "max_iterations": 5,
    "confidence": 0.80,
    "terminal_action": None,
    "rationale": None,
    "current_tool_request": {
        "action": "reverify_alternate_source",
        "arguments": {"field_name": "applicant_name", "applicant_id": "APP-TEST-001"},
        "rationale": "Trying to reverify the same field again",
        "confidence": 0.80,
    },
    "guardrail_violations": [],
    "requires_human_approval": False,
}

print("Proposed tool request by Agent:")
print(json.dumps(state["current_tool_request"], indent=2))

# Allowlist gate node execution
updates = allowlist_gate(state)

print("\nAllowlist Gate Result:")
print("Violations recorded:", updates["guardrail_violations"])
print("Overridden next action:")
print(json.dumps(updates["current_tool_request"], indent=2))

print("\n" + "=" * 70)
print("TEST 2: Agent attempts to call terminal tool twice (e.g. auto_clear)")
print("=" * 70)

terminal_history = [
    {
        "call": {
            "tool_name": "auto_clear",
            "arguments": {"reason": "Cleared low discrepancy"},
            "rationale": "Initial clear",
        },
        "result": {"tool_name": "auto_clear", "success": True},
    }
]

is_allowed, reason = validate_tool_call("auto_clear", terminal_history)
print(f"Tool: auto_clear (called a 2nd time)")
print(f"Is Allowed: {is_allowed}")
print(f"Rejection Reason: {reason}")
print("=" * 70)

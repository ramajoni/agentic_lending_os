"""
Guard 4 — Tool/API allowlist enforcement.

Hard-enforced gate before every tool execution in the agent loop.
Validates:
  (a) Tool name is in the configured allowlist
  (b) Terminal tools aren't re-used (can't escalate twice)
  (c) Contextual constraints (can't auto_clear if fraud watchlist hit)
"""

import json
from pathlib import Path
from app.config.logger import get_logger
from app.config.app_constants import agent_config

log = get_logger(__name__)

# Directory where per-agent JSON configuration files are stored
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "app" / "config" / "agents"
DEFAULT_AGENT_ID = "discrepancy_investigation_agent"

# Terminal tools — these end the investigation
TERMINAL_TOOLS = {"request_additional_document", "escalate_to_human", "auto_clear"}

# Non-terminal tools — these must be followed by another reasoning step
NON_TERMINAL_TOOLS = {
    "reverify_alternate_source",
    "verify_pan",
    "verify_aadhaar",
    "query_historical_cases",
    "check_fraud_watchlist",
}

ALL_TOOLS = TERMINAL_TOOLS | NON_TERMINAL_TOOLS


def load_agent_policy(agent_id: str = DEFAULT_AGENT_ID) -> dict:
    """Load an agent's tool policy from configs/agents/{agent_id}.json at runtime.

    Allows hot-reloading tool permissions without restarting services.
    Falls back gracefully to agent_config if the file is not found.

    Args:
        agent_id: The ID of the agent (e.g. 'discrepancy_investigation_agent', 'underwriter_agent')

    Returns:
        Dict containing agent policy with allowlisted_tools and terminal_tools.
    """
    config_file = CONFIG_DIR / f"{agent_id}.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                policy = json.load(f)
                return policy
        except Exception as e:
            log.warning("Failed to load agent policy from %s: %s. Falling back to default config.", config_file, e)

    return {
        "agent_id": agent_id,
        "allowlisted_tools": agent_config.allowlisted_tools,
        "terminal_tools": list(TERMINAL_TOOLS),
    }


def get_allowlisted_tools_for_agent(agent_id: str = DEFAULT_AGENT_ID) -> list[str]:
    """Get the current list of allowed tools for a specific agent."""
    policy = load_agent_policy(agent_id)
    return policy.get("allowlisted_tools", agent_config.allowlisted_tools)


class ToolNotAllowedError(Exception):
    """Raised when a tool call is rejected by the allowlist gate."""

    def __init__(self, tool_name: str, reason: str):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool '{tool_name}' blocked: {reason}")


def validate_tool_call(
    tool_name: str,
    tool_call_history: list[dict],
    state: dict | None = None,
    agent_id: str = DEFAULT_AGENT_ID,
    arguments: dict | None = None,
) -> tuple[bool, str | None]:
    """Validate whether a tool call is permitted given current state and agent policy.

    Reads the agent's policy from JSON at runtime, enabling dynamic per-agent
    allowlists.

    Args:
        tool_name: Name of the tool the agent wants to call.
        tool_call_history: List of previous ToolCallRecord dicts.
        state: Current investigation state (for contextual rules and optional agent_id).
        agent_id: Identifier of the agent making the call.

    Returns:
        (is_allowed, rejection_reason_or_None)
    """
    # Prefer agent_id from state if available
    if state and isinstance(state, dict) and state.get("agent_id"):
        agent_id = state["agent_id"]

    policy = load_agent_policy(agent_id)
    allowed_tools = policy.get("allowlisted_tools", agent_config.allowlisted_tools)
    terminal_tools = set(policy.get("terminal_tools", TERMINAL_TOOLS))

    # (a) Check tool is in the agent's configured allowlist
    if tool_name not in allowed_tools:
        reason = f"Tool '{tool_name}' is not in the allowlist for agent '{agent_id}': {allowed_tools}"
        log.warning("Guard 4 BLOCKED — %s", reason)
        return False, reason

    # (b) Check terminal tools aren't re-used
    if tool_name in terminal_tools:
        used_terminals = {
            record.get("call", {}).get("tool_name")
            for record in tool_call_history
            if record.get("call", {}).get("tool_name") in terminal_tools
        }
        if tool_name in used_terminals:
            reason = f"Terminal tool '{tool_name}' has already been used in this investigation"
            log.warning("Guard 4 BLOCKED — %s", reason)
            return False, reason

    # (c) Check duplicate / repeated tool calls
    allow_repeated = policy.get("allow_repeated_tool_calls", True)
    req_args = arguments
    if req_args is None and state and isinstance(state, dict):
        req_args = state.get("current_tool_request", {}).get("arguments")

    for record in tool_call_history:
        call = record.get("call", {})
        if call.get("tool_name") == tool_name:
            if not allow_repeated:
                reason = f"Tool '{tool_name}' has already been used in this investigation (repeated calls not permitted for agent '{agent_id}')"
                log.warning("Guard 4 BLOCKED — %s", reason)
                return False, reason
            if req_args is not None and call.get("arguments") == req_args:
                reason = f"Tool '{tool_name}' has already been called with identical arguments in this investigation"
                log.warning("Guard 4 BLOCKED — %s", reason)
                return False, reason

    # (d) Contextual constraints
    if tool_name == "auto_clear" and state is not None:
        # Can't auto-clear if fraud watchlist returned a positive hit
        for record in tool_call_history:
            call = record.get("call", {})
            result = record.get("result", {})
            if (
                call.get("tool_name") == "check_fraud_watchlist"
                and result.get("result", {}).get("is_match", False)
            ):
                reason = "Cannot auto_clear: fraud watchlist returned a positive hit"
                log.warning("Guard 4 BLOCKED — %s", reason)
                return False, reason

    # (e) Protected identity service token check
    if tool_name in {"verify_pan", "verify_aadhaar"}:
        has_token = False
        if req_args is not None:
            has_token = bool(req_args.get("token") or req_args.get("service_token") or req_args.get("auth_token"))
        if not has_token:
            reason = f"Tool '{tool_name}' requires an authorized service token to access protected identity services"
            log.warning("Guard 4 BLOCKED — %s", reason)
            return False, reason

    log.info("Guard 4 PASSED — tool '%s' is allowed for agent '%s'", tool_name, agent_id)
    return True, None


def assert_tool_allowed(
    tool_name: str,
    tool_call_history: list[dict],
    state: dict | None = None,
    agent_id: str = DEFAULT_AGENT_ID,
    arguments: dict | None = None,
) -> None:
    """Validate and raise if tool is not allowed.

    Convenience wrapper for use as a gate node in the graph.
    """
    is_allowed, reason = validate_tool_call(
        tool_name, tool_call_history, state, agent_id=agent_id, arguments=arguments
    )
    if not is_allowed:
        raise ToolNotAllowedError(tool_name, reason)

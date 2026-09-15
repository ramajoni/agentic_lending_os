"""
Verification agent graph nodes.
"""

import inspect
from agent.verification.state import InvestigationState
from app.models.investigation import InvestigationDecision
from app.models.tool_call import ToolCall, ToolResult, ToolCallRecord
from agent.verification.reasoning import invoke_reasoning
from agent.verification.tools import TOOL_REGISTRY, TERMINAL_TOOLS
from agent.verification.guardrails.tool_allowlist import validate_tool_call
from agent.verification.guardrails.confidence_router import evaluate_confidence
from agent.verification.guardrails.critical_action_gate import apply_approval_gate
from app.shared.guardrails.pii_redactor import redact_for_logging
from app.config.app_constants import agent_config
from app.config.logger import get_logger

log = get_logger(__name__)


def init_node(state: InvestigationState) -> dict:
    """Load discrepancies from DAG output into state."""
    agent_id = state.get("agent_id", "discrepancy_investigation_agent")
    log.info("═══ AGENT INIT — applicant %s (%s), %d discrepancies ═══",
             state["applicant_id"], agent_id, len(state["discrepancies"]))
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


def tool_execution_node(state: InvestigationState) -> dict:
    """Execute the selected tool and append result to history."""
    request = state.get("current_tool_request", {})
    tool_name = request.get("action", "")
    arguments = request.get("arguments", {})
    rationale = request.get("rationale", "")

    arguments["applicant_id"] = state.get("applicant_id", "")

    tool_fn = TOOL_REGISTRY.get(tool_name)
    if not tool_fn:
        log.error("Tool '%s' not found in registry", tool_name)
        result = ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Tool '{tool_name}' not found in registry",
        )
    else:
        try:
            sig = inspect.signature(tool_fn)
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            call_args = (
                arguments
                if has_var_keyword
                else {k: v for k, v in arguments.items() if k in sig.parameters}
            )
            raw_result = tool_fn(**call_args)
            result = ToolResult(
                tool_name=tool_name,
                success=True,
                result=raw_result,
            )
            log.info("Tool '%s' executed successfully", tool_name)
        except Exception as e:
            log.error("Tool '%s' execution failed: %s", tool_name, e)
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    call_record = ToolCallRecord(
        call=ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            rationale=rationale,
        ),
        result=result,
    )

    history = list(state.get("tool_call_history", []))
    history.append(call_record.model_dump())

    redacted = redact_for_logging(call_record.model_dump())
    log.info("Tool call record (redacted): %s", redacted)

    updates = {"tool_call_history": history}
    if tool_name in TERMINAL_TOOLS:
        updates["terminal_action"] = tool_name

    return updates


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


def critical_action_gate_node(state: InvestigationState) -> dict:
    """Guard 10 — non-blocking approval gate for terminal actions."""
    updated = apply_approval_gate(dict(state))
    return {
        "requires_human_approval": updated.get("requires_human_approval", True),
    }


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


def route_after_loop_check(state: InvestigationState) -> str:
    """Determine the next node after loop_check."""
    if state.get("terminal_action"):
        return "critical_action_gate"
    return "reasoning"

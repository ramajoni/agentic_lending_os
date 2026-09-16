"""
Tool execution node for verification agent graph.
Executes the selected tool and records results into history.
"""

import inspect
from agent.verification.state import InvestigationState
from agent.verification.tools import TOOL_REGISTRY, TERMINAL_TOOLS
from app.models.tool_call import ToolCall, ToolResult, ToolCallRecord
from app.guardrails.pii_redactor import redact_for_logging
from app.config.logger import get_logger

log = get_logger(__name__)


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


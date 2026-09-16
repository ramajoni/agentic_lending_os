"""
Tracing and execution logging helpers for agents.
"""

from app.config.logger import get_logger
from app.guardrails.pii_redactor import redact_for_logging

log = get_logger(__name__)


def trace_tool_execution(tool_name: str, arguments: dict, result: dict) -> None:
    """Log redacted tool execution details."""
    payload = {
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
    }
    redacted = redact_for_logging(payload)
    log.info("Agent Tool Trace: %s", redacted)

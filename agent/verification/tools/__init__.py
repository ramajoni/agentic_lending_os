"""Agent tools — one module per investigation tool (all mocked)."""

from agent.verification.tools.reverify_alternate_source import reverify_alternate_source
from agent.verification.tools.verify_pan import verify_pan
from agent.verification.tools.verify_aadhaar import verify_aadhaar
from agent.verification.tools.request_additional_document import request_additional_document
from agent.verification.tools.query_historical_cases import query_historical_cases
from agent.verification.tools.check_fraud_watchlist import check_fraud_watchlist
from agent.verification.tools.escalate_to_human import escalate_to_human
from agent.verification.tools.auto_clear import auto_clear

# ── Tool registry ────────────────────────────────────────────────────────────
TOOL_REGISTRY: dict[str, callable] = {
    "reverify_alternate_source": reverify_alternate_source,
    "verify_pan": verify_pan,
    "verify_aadhaar": verify_aadhaar,
    "request_additional_document": request_additional_document,
    "query_historical_cases": query_historical_cases,
    "check_fraud_watchlist": check_fraud_watchlist,
    "escalate_to_human": escalate_to_human,
    "auto_clear": auto_clear,
}

TERMINAL_TOOLS = {"request_additional_document", "escalate_to_human", "auto_clear"}
NON_TERMINAL_TOOLS = {
    "reverify_alternate_source",
    "verify_pan",
    "verify_aadhaar",
    "query_historical_cases",
    "check_fraud_watchlist",
}

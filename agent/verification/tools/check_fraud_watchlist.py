"""
Tool: check_fraud_watchlist

Cross-references discrepancy patterns against known fraud signatures.
Non-terminal.
"""

from app.config.logger import get_logger

log = get_logger(__name__)

# Mock fraud watchlist — keyed by PAN prefix for scenario control
_WATCHLIST: dict[str, dict] = {
    # Scenario 3: positive fraud hit
    "KLMNO9012P": {
        "is_match": True,
        "match_type": "income_inflation_pattern",
        "risk_score": 0.85,
        "details": "PAN associated with multiple loan applications showing consistent income over-declaration (3 cases in last 12 months)",
        "recommended_action": "escalate_to_human",
    },
}


def check_fraud_watchlist(
    pan_number: str = "",
    applicant_name: str = "",
    discrepancy_types: list[str] | None = None,
    applicant_id: str = "",
) -> dict:
    """Cross-reference against known fraud signatures.

    Args:
        pan_number: PAN for watchlist lookup.
        applicant_name: Name for fuzzy matching.
        discrepancy_types: Types of discrepancies found.
        applicant_id: For logging context.

    Returns:
        Dict with watchlist match results.
    """
    log.info(
        "Tool [check_fraud_watchlist] — PAN='%s', applicant='%s'",
        (pan_number[:5] + "XXXXX") if pan_number else "N/A",
        applicant_id,
    )

    result = _WATCHLIST.get(pan_number)
    if result:
        log.warning(
            "Tool [check_fraud_watchlist] — MATCH FOUND: type='%s', risk=%.2f",
            result["match_type"],
            result["risk_score"],
        )
        return {
            "tool": "check_fraud_watchlist",
            **result,
        }

    log.info("Tool [check_fraud_watchlist] — no matches found")
    return {
        "tool": "check_fraud_watchlist",
        "is_match": False,
        "match_type": None,
        "risk_score": 0.0,
        "details": "No fraud watchlist matches found",
        "recommended_action": None,
    }

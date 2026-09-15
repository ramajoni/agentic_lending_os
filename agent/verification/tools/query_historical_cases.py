"""
Tool: query_historical_cases

Checks if this discrepancy pattern has occurred before for this
applicant or similar applicant segments. Non-terminal.
"""

from app.config.logger import get_logger

log = get_logger(__name__)

# Mock historical case data
_HISTORICAL_DB: dict[str, list[dict]] = {
    "name_mismatch": [
        {
            "case_id": "HIST-2024-001",
            "outcome": "auto_cleared",
            "reason": "Abbreviation difference in middle name",
            "frequency": "common",
        },
    ],
    "address_mismatch": [
        {
            "case_id": "HIST-2024-015",
            "outcome": "auto_cleared",
            "reason": "Format difference, same physical address",
            "frequency": "common",
        },
        {
            "case_id": "HIST-2024-032",
            "outcome": "escalated",
            "reason": "Completely different city — relocation without update",
            "frequency": "uncommon",
        },
    ],
    "income_mismatch": [
        {
            "case_id": "HIST-2024-042",
            "outcome": "escalated",
            "reason": "Significant over-declaration pattern",
            "frequency": "flagged",
        },
    ],
}


def query_historical_cases(
    discrepancy_type: str = "",
    severity: str = "",
    applicant_id: str = "",
    **kwargs,
) -> dict:
    """Check historical cases for similar discrepancy patterns.

    Args:
        discrepancy_type: Type of discrepancy (e.g., 'name_mismatch').
        severity: Severity level for filtering.
        applicant_id: For logging context.

    Returns:
        Dict with historical case matches and pattern analysis.
    """
    log.info(
        "Tool [query_historical_cases] — type='%s', severity='%s', applicant='%s'",
        discrepancy_type, severity, applicant_id,
    )

    cases = _HISTORICAL_DB.get(discrepancy_type, [])

    return {
        "tool": "query_historical_cases",
        "discrepancy_type": discrepancy_type,
        "historical_matches": cases,
        "total_matches": len(cases),
        "pattern_summary": (
            f"Found {len(cases)} historical case(s) for '{discrepancy_type}'. "
            + (
                f"Most common outcome: {cases[0]['outcome']}."
                if cases
                else "No prior cases found — this is a novel pattern."
            )
        ),
    }

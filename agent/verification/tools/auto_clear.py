"""
Tool: auto_clear

Closes out a discrepancy as benign. TERMINAL — ends the investigation.
"""

from app.config.logger import get_logger

log = get_logger(__name__)


def auto_clear(
    reason: str,
    discrepancy_types_cleared: list[str] | None = None,
    applicant_id: str = "",
) -> dict:
    """Close discrepancies as benign — no further action needed.

    Args:
        reason: Why the discrepancies are considered benign.
        discrepancy_types_cleared: Which discrepancy types are being cleared.
        applicant_id: For logging context.

    Returns:
        Dict confirming the auto-clear.
    """
    log.info(
        "Tool [auto_clear] — clearing %s for applicant '%s'",
        discrepancy_types_cleared or "all", applicant_id,
    )

    return {
        "tool": "auto_clear",
        "is_terminal": True,
        "status": "discrepancies_cleared",
        "reason": reason,
        "discrepancy_types_cleared": discrepancy_types_cleared or [],
        "message": "All flagged discrepancies have been reviewed and cleared as benign.",
        "applicant_id": applicant_id,
    }

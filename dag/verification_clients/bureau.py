"""
Mock credit bureau check service.

Returns credit score, existing loans, and income estimate.
"""

import asyncio
from app.config.logger import get_logger

log = get_logger(__name__)

# ── Mock bureau database ─────────────────────────────────────────────────────
_BUREAU_DB: dict[str, dict] = {
    # Scenario 1: income matches well
    "ABCDE1234F": {
        "credit_score": 750,
        "existing_loans": 1,
        "total_outstanding": 500000,
        "income_estimate": 1200000,  # 12L — applicant declares 12L
        "delinquency_flag": False,
    },
    # Scenario 2: slight income discrepancy (within tolerance)
    "FGHIJ5678K": {
        "credit_score": 680,
        "existing_loans": 2,
        "total_outstanding": 800000,
        "income_estimate": 900000,  # 9L — applicant declares 10L
        "delinquency_flag": False,
    },
    # Scenario 3: significant income mismatch
    "KLMNO9012P": {
        "credit_score": 620,
        "existing_loans": 3,
        "total_outstanding": 2500000,
        "income_estimate": 800000,  # 8L — applicant declares 15L (87.5% deviation)
        "delinquency_flag": True,
    },
}


async def check_bureau(pan_number: str, dob: str = "") -> dict:
    """Run a credit bureau check using PAN as the primary identifier.

    Args:
        pan_number: PAN in ABCDE1234F format.
        dob: Date of birth for additional verification.

    Returns:
        Dict with credit_score, existing_loans, income_estimate, etc.
    """
    log.info("Mock bureau check for PAN: %s", pan_number[:5] + "XXXXX")

    await asyncio.sleep(0.15)

    record = _BUREAU_DB.get(pan_number)
    if record:
        log.info(
            "Mock bureau — record found (score=%d, income_est=%s)",
            record["credit_score"],
            record["income_estimate"],
        )
        return {**record, "pan_number": pan_number, "verified": True}

    log.warning("Mock bureau — no record found for %s", pan_number[:5] + "XXXXX")
    return {
        "pan_number": pan_number,
        "verified": False,
        "credit_score": 0,
        "income_estimate": 0,
    }

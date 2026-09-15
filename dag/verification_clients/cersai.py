"""
Mock CERSAI check service.

Returns existing charges/encumbrances on assets.
"""

import asyncio
from app.config.logger import get_logger

log = get_logger(__name__)

# ── Mock CERSAI database ─────────────────────────────────────────────────────
_CERSAI_DB: dict[str, dict] = {
    # Scenario 1: no charges
    "ABCDE1234F": {
        "has_existing_charge": False,
        "charge_details": "",
        "assets_checked": 1,
    },
    # Scenario 2: no charges
    "FGHIJ5678K": {
        "has_existing_charge": False,
        "charge_details": "",
        "assets_checked": 1,
    },
    # Scenario 3: no charges (income + fraud are the issue, not property)
    "KLMNO9012P": {
        "has_existing_charge": False,
        "charge_details": "",
        "assets_checked": 1,
    },
}


async def check_cersai(pan_number: str = "", aadhaar_number: str = "", property_id: str = "") -> dict:
    """Check CERSAI for existing charges on the applicant's assets.

    Args:
        pan_number: PAN for lookup.
        aadhaar_number: Aadhaar for lookup.
        property_id: Specific property ID if available.

    Returns:
        Dict with has_existing_charge, charge_details, etc.
    """
    identifier = pan_number or aadhaar_number or property_id
    log.info("Mock CERSAI check for: %s", identifier[:5] + "..." if identifier else "N/A")

    await asyncio.sleep(0.1)

    # Look up by PAN first, then Aadhaar
    record = _CERSAI_DB.get(pan_number) or _CERSAI_DB.get(aadhaar_number)
    if record:
        log.info("Mock CERSAI — record found (charges=%s)", record["has_existing_charge"])
        return {**record, "verified": True}

    log.info("Mock CERSAI — no record found, assuming clean")
    return {
        "has_existing_charge": False,
        "charge_details": "",
        "verified": True,
        "assets_checked": 0,
    }

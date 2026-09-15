"""
Mock GST verification service.

Returns business name and address associated with a GSTIN.
"""

import asyncio
from app.config.logger import get_logger

log = get_logger(__name__)

# ── Mock GST database ────────────────────────────────────────────────────────
_GST_DB: dict[str, dict] = {
    # Scenario 1: matches fine
    "27ABCDE1234F1Z5": {
        "business_name": "Rajesh Kumar Sharma",
        "business_address": "42, MG Road, Andheri West, Mumbai 400053",
        "status": "active",
        "registration_date": "2018-04-01",
    },
    # Scenario 2: will time out (simulated)
    "29FGHIJ5678K1Z3": {
        "business_name": "Priya Nair Enterprises",
        "business_address": "15, Brigade Road, Bangalore 560001",
        "status": "active",
        "registration_date": "2019-07-15",
        "_simulate_timeout": True,
    },
    # Scenario 3: matches
    "07KLMNO9012P1Z8": {
        "business_name": "Amit Verma Trading Co",
        "business_address": "88, Connaught Place, New Delhi 110001",
        "status": "active",
        "registration_date": "2017-11-01",
    },
}


async def verify_gst(gst_number: str) -> dict:
    """Look up a GSTIN and return associated business details.

    Args:
        gst_number: GSTIN in standard format.

    Returns:
        Dict with business_name, business_address, status.
    """
    log.info("Mock GST verification for: %s", gst_number[:4] + "...")

    # Simulate network latency
    await asyncio.sleep(0.1)

    record = _GST_DB.get(gst_number)
    if record:
        # Simulate timeout for specific test scenarios
        if record.get("_simulate_timeout"):
            log.warning("Mock GST — simulating timeout for %s", gst_number[:4] + "...")
            return {
                "gst_number": gst_number,
                "verified": False,
                "timed_out": True,
                "business_name": "",
                "business_address": "",
            }

        log.info("Mock GST — record found for %s", gst_number[:4] + "...")
        result = {k: v for k, v in record.items() if not k.startswith("_")}
        return {**result, "gst_number": gst_number, "verified": True}

    log.warning("Mock GST — no record found for %s", gst_number[:4] + "...")
    return {
        "gst_number": gst_number,
        "verified": False,
        "business_name": "",
        "business_address": "",
        "status": "not_found",
    }

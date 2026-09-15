"""
Mock Aadhaar verification service.

Returns the name, DOB, and address associated with an Aadhaar number.
Requires a valid service token to access the Aadhaar service.
"""

import asyncio
import re
from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)

# ── Mock Aadhaar database ───────────────────────────────────────────────────
# Keyed by 12-digit Aadhaar number
_AADHAAR_DB: dict[str, dict] = {
    # Scenario 1: trivial case
    "234567890123": {
        "name": "Rajesh K Sharma",
        "dob": "1985-06-15",
        "address": "Flat 402, Sunshine Heights, Mumbai - 400053",
        "status": "active",
    },
    # Scenario 2: compounding weak signals
    "345678901234": {
        "name": "Priya Nair",
        "dob": "1990-03-22",
        "address": "42 MG Road, Andheri West, Mumbai - 400053",
        "status": "active",
    },
    # Scenario 3: escalation-forcing
    "456789012345": {
        "name": "Amit Verma",
        "dob": "1988-11-10",
        "address": "78 Sector 15, Gurgaon - 122001",
        "status": "active",
    },
}


async def verify_aadhaar(aadhaar_number: str, token: str | None = None) -> dict:
    """Look up an Aadhaar number and return associated identity details.

    Requires a valid service token to access the Aadhaar service.

    Args:
        aadhaar_number: 12-digit Aadhaar number.
        token: Service authentication token.

    Returns:
        Dict with name, dob, address, status — or unauthorized/error flag.
    """
    clean_num = re.sub(r"\s", "", aadhaar_number or "")
    masked_aadhaar = (clean_num[:4] + "XXXX" + clean_num[-4:]) if len(clean_num) >= 8 else "INVALID"
    log.info("Mock Aadhaar verification for: %s", masked_aadhaar)

    # Guard: Service token authorization check
    if not token or token != api_config.aadhaar_service_token:
        log.warning("Mock Aadhaar verification REJECTED — missing or invalid service token")
        return {
            "aadhaar_number": clean_num,
            "verified": False,
            "status": "unauthorized",
            "error": "UNAUTHORIZED: Valid service token required to access Aadhaar service",
        }

    # Simulate network latency
    await asyncio.sleep(0.1)

    record = _AADHAAR_DB.get(clean_num)
    if record:
        log.info("Mock Aadhaar — record found for %s", masked_aadhaar)
        return {**record, "aadhaar_number": clean_num, "verified": True}

    log.warning("Mock Aadhaar — no record found for %s", masked_aadhaar)
    return {
        "aadhaar_number": clean_num,
        "verified": False,
        "name": "",
        "dob": "",
        "address": "",
        "status": "not_found",
    }

"""
Mock PAN verification service.

Returns the name and DOB associated with a PAN number.
Different applicant_ids trigger different mock scenarios.
"""

import asyncio
from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)

# ── Mock PAN database ────────────────────────────────────────────────────────
# Keyed by PAN number → (name, dob)
_PAN_DB: dict[str, dict] = {
    # Scenario 1: trivial case — minor spelling variation
    "ABCDE1234F": {
        "name": "Rajesh Kumar Sharma",  # Applicant may say "Rajesh K Sharma"
        "dob": "1985-06-15",
        "status": "active",
    },
    # Scenario 2: compounding weak signals
    "FGHIJ5678K": {
        "name": "Priya Nair",
        "dob": "1990-03-22",
        "status": "active",
    },
    # Scenario 3: escalation-forcing
    "KLMNO9012P": {
        "name": "Amit Verma",
        "dob": "1988-11-10",
        "status": "active",
    },
}


async def verify_pan(pan_number: str, token: str | None = None) -> dict:
    """Look up a PAN number and return associated identity details.

    Requires a valid service token to access the PAN service.

    Args:
        pan_number: PAN in ABCDE1234F format.
        token: Service authentication token.

    Returns:
        Dict with name, dob, status — or unauthorized/error flag.
    """
    log.info("Mock PAN verification for: %s", pan_number[:5] + "XXXXX" if pan_number else "EMPTY")

    # Guard: Service token authorization check
    if not token or token != api_config.pan_service_token:
        log.warning("Mock PAN verification REJECTED — missing or invalid service token")
        return {
            "pan_number": pan_number,
            "verified": False,
            "status": "unauthorized",
            "error": "UNAUTHORIZED: Valid service token required to access PAN service",
        }

    # Simulate network latency
    await asyncio.sleep(0.1)

    record = _PAN_DB.get(pan_number)
    if record:
        log.info("Mock PAN — record found for %s", pan_number[:5] + "XXXXX")
        return {**record, "pan_number": pan_number, "verified": True}

    log.warning("Mock PAN — no record found for %s", pan_number[:5] + "XXXXX")
    return {
        "pan_number": pan_number,
        "verified": False,
        "name": "",
        "dob": "",
        "status": "not_found",
    }

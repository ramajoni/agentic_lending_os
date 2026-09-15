"""
Tool: verify_aadhaar

Calls the Aadhaar verification service to check identity and address details.
Requires a valid service authentication token.
Non-terminal — must be followed by another reasoning step.
"""

import asyncio
from dag.verification_clients.aadhaar import verify_aadhaar as mock_verify_aadhaar
from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)


def verify_aadhaar(
    aadhaar_number: str = "",
    token: str = "",
    service_token: str = "",
    applicant_id: str = "",
    **kwargs,
) -> dict:
    """Execute Aadhaar verification service call.

    Args:
        aadhaar_number: 12-digit Aadhaar number to verify.
        token: Service authentication token.
        service_token: Alias for token.
        applicant_id: For logging context.

    Returns:
        Dict with Aadhaar verification result or unauthorized error.
    """
    auth_token = token or service_token or kwargs.get("auth_token", "")
    log.info(
        "Tool [verify_aadhaar] — aadhaar='%s', applicant='%s', token_provided=%s",
        (aadhaar_number[:4] + "XXXX" + aadhaar_number[-4:]) if len(aadhaar_number) >= 8 else "INVALID",
        applicant_id,
        bool(auth_token),
    )

    if not auth_token:
        log.warning("Tool [verify_aadhaar] BLOCKED — missing service token")
        return {
            "tool": "verify_aadhaar",
            "success": False,
            "error": "UNAUTHORIZED: Valid service token required to access Aadhaar service. The agent cannot call this tool without a valid token.",
            "aadhaar_number": aadhaar_number,
        }

    # Call async mock service synchronously within tool
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, mock_verify_aadhaar(aadhaar_number, token=auth_token)).result()
        else:
            res = loop.run_until_complete(mock_verify_aadhaar(aadhaar_number, token=auth_token))
    except Exception:
        res = asyncio.run(mock_verify_aadhaar(aadhaar_number, token=auth_token))

    if res.get("status") == "unauthorized" or not res.get("verified", False) and "UNAUTHORIZED" in str(res.get("error", "")):
        return {
            "tool": "verify_aadhaar",
            "success": False,
            "error": res.get("error", "UNAUTHORIZED: Invalid service token for Aadhaar service."),
            "aadhaar_number": aadhaar_number,
        }

    return {
        "tool": "verify_aadhaar",
        "success": True,
        "aadhaar_number": aadhaar_number,
        "name": res.get("name"),
        "dob": res.get("dob"),
        "address": res.get("address"),
        "status": res.get("status"),
        "verified": res.get("verified"),
    }

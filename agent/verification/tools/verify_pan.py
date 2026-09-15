"""
Tool: verify_pan

Calls the PAN verification service to check identity details.
Requires a valid service authentication token.
Non-terminal — must be followed by another reasoning step.
"""

import asyncio
from dag.verification_clients.pan import verify_pan as mock_verify_pan
from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)


def verify_pan(
    pan_number: str = "",
    token: str = "",
    service_token: str = "",
    applicant_id: str = "",
    **kwargs,
) -> dict:
    """Execute PAN verification service call.

    Args:
        pan_number: The 10-character PAN number to verify.
        token: Service authentication token.
        service_token: Alias for token.
        applicant_id: For logging context.

    Returns:
        Dict with PAN verification result or unauthorized error.
    """
    auth_token = token or service_token or kwargs.get("auth_token", "")
    log.info(
        "Tool [verify_pan] — pan='%s', applicant='%s', token_provided=%s",
        pan_number[:5] + "XXXXX" if pan_number else "EMPTY",
        applicant_id,
        bool(auth_token),
    )

    if not auth_token:
        log.warning("Tool [verify_pan] BLOCKED — missing service token")
        return {
            "tool": "verify_pan",
            "success": False,
            "error": "UNAUTHORIZED: Valid service token required to access PAN service. The agent cannot call this tool without a valid token.",
            "pan_number": pan_number,
        }

    # Call async mock service synchronously within tool
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, mock_verify_pan(pan_number, token=auth_token)).result()
        else:
            res = loop.run_until_complete(mock_verify_pan(pan_number, token=auth_token))
    except Exception:
        res = asyncio.run(mock_verify_pan(pan_number, token=auth_token))

    if res.get("status") == "unauthorized" or not res.get("verified", False) and "UNAUTHORIZED" in str(res.get("error", "")):
        return {
            "tool": "verify_pan",
            "success": False,
            "error": res.get("error", "UNAUTHORIZED: Invalid service token for PAN service."),
            "pan_number": pan_number,
        }

    return {
        "tool": "verify_pan",
        "success": True,
        "pan_number": pan_number,
        "name": res.get("name"),
        "dob": res.get("dob"),
        "status": res.get("status"),
        "verified": res.get("verified"),
    }

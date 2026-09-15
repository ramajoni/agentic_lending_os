"""
DAG Node 2 — Parallel verification calls.

Runs PAN, GST, Bureau, and CERSAI verification concurrently
with Guard 5 (parameter validation) applied before each call.
"""

import asyncio
from app.models.applicant import ExtractedFields
from app.config.app_constants import api_config
from dag.guardrails.api_validator import validate_api_params, APIValidationError
from dag.verification_clients import (
    verify_pan,
    verify_aadhaar,
    verify_gst,
    check_bureau,
    check_cersai,
)
from app.config.logger import get_logger

log = get_logger(__name__)


async def _safe_verify(api_name: str, coro):
    """Wrap a verification call with error handling.

    Returns the result or an error dict — never raises.
    """
    try:
        return await coro
    except APIValidationError as e:
        log.warning("Verification '%s' skipped — validation error: %s", api_name, e.errors)
        return {"verified": False, "error": str(e), "api": api_name}
    except asyncio.TimeoutError:
        log.warning("Verification '%s' timed out", api_name)
        return {"verified": False, "timed_out": True, "api": api_name}
    except Exception as e:
        log.error("Verification '%s' failed unexpectedly: %s", api_name, e)
        return {"verified": False, "error": str(e), "api": api_name}


async def run_parallel_verification(
    extracted: ExtractedFields,
    dob: str = "",
) -> dict[str, dict]:
    """Run all verification calls in parallel.

    Guard 5 validates parameters before each call.

    Args:
        extracted: Extracted fields from documents.
        dob: Date of birth for bureau check.

    Returns:
        Dict mapping api_name → result dict.
    """
    log.info("DAG verification — starting parallel checks for %s", extracted.applicant_id)

    results = {}

    # ── Prepare and validate params ──────────────────────────────────────
    tasks = {}

    # PAN verification (requires service token)
    if extracted.pan_number:
        try:
            validate_api_params("pan", {
                "pan_number": extracted.pan_number,
                "token": api_config.pan_service_token,
            })
            tasks["pan"] = verify_pan(
                extracted.pan_number,
                token=api_config.pan_service_token,
            )
        except APIValidationError as e:
            results["pan"] = {"verified": False, "error": str(e)}

    # Aadhaar verification (requires service token)
    if extracted.aadhaar_number:
        try:
            validate_api_params("aadhaar", {
                "aadhaar_number": extracted.aadhaar_number,
                "token": api_config.aadhaar_service_token,
            })
            tasks["aadhaar"] = verify_aadhaar(
                extracted.aadhaar_number,
                token=api_config.aadhaar_service_token,
            )
        except APIValidationError as e:
            results["aadhaar"] = {"verified": False, "error": str(e)}

    # GST verification
    if extracted.gst_number:
        try:
            validate_api_params("gst", {"gst_number": extracted.gst_number})
            tasks["gst"] = verify_gst(extracted.gst_number)
        except APIValidationError as e:
            results["gst"] = {"verified": False, "error": str(e)}

    # Bureau check
    if extracted.pan_number:
        try:
            validate_api_params("bureau", {
                "pan_number": extracted.pan_number,
                "dob": dob,
            })
            tasks["bureau"] = check_bureau(extracted.pan_number, dob)
        except APIValidationError as e:
            results["bureau"] = {"verified": False, "error": str(e)}

    # CERSAI check
    if extracted.pan_number or extracted.aadhaar_number:
        try:
            validate_api_params("cersai", {
                "pan_number": extracted.pan_number,
                "aadhaar_number": extracted.aadhaar_number,
            })
            tasks["cersai"] = check_cersai(
                pan_number=extracted.pan_number,
                aadhaar_number=extracted.aadhaar_number,
            )
        except APIValidationError as e:
            results["cersai"] = {"verified": False, "error": str(e)}

    # ── Execute in parallel ──────────────────────────────────────────────
    if tasks:
        api_names = list(tasks.keys())
        coros = [_safe_verify(name, coro) for name, coro in tasks.items()]
        completed = await asyncio.gather(*coros)
        for name, result in zip(api_names, completed):
            results[name] = result

    log.info(
        "DAG verification — completed. APIs called: %s",
        list(results.keys()),
    )
    return results

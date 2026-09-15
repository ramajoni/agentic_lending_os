"""
Tool: reverify_alternate_source

Re-checks a mismatched field against a different verification source.
E.g., if PAN name doesn't match, try Aadhaar-linked lookup.
Non-terminal — must be followed by another reasoning step.
"""

from app.config.app_constants import api_config
from app.config.logger import get_logger

log = get_logger(__name__)

# Mock alternate verification results based on field + scenario
_ALTERNATE_RESULTS: dict[str, dict] = {
    "applicant_name": {
        "source": "Aadhaar-linked lookup",
        "verified_value": "Rajesh K Sharma",  # closer to "Rajesh K Sharma"
        "match_confidence": 0.95,
        "notes": "Aadhaar record shows abbreviated middle name — likely the same person",
    },
    "address": {
        "source": "Aadhaar address database",
        "verified_value": "42 MG Road, Andheri West, Mumbai - 400053",
        "match_confidence": 0.80,
        "notes": "Address format differs but location matches",
    },
    "annual_income": {
        "source": "ITR e-filing records",
        "verified_value": "1250000",
        "match_confidence": 0.70,
        "notes": "ITR shows slightly different figure due to deductions",
    },
}


def reverify_alternate_source(
    field_name: str = "",
    declared_value: str = "",
    original_source: str = "",
    applicant_id: str = "",
    token: str = "",
    service_token: str = "",
    **kwargs,
) -> dict:
    """Re-verify a field against an alternate source.

    Protected identity sources (Aadhaar and PAN) require a valid service authentication token.

    Args:
        field_name: The field to re-verify (e.g., 'applicant_name').
        declared_value: The value declared by the applicant.
        original_source: The source that first flagged the mismatch.
        applicant_id: For logging context.
        token: Service authentication token.
        service_token: Alias for token.

    Returns:
        Dict with alternate verification result or unauthorized error.
    """
    auth_token = token or service_token or kwargs.get("auth_token", "")
    log.info(
        "Tool [reverify_alternate_source] — field='%s', original_source='%s', applicant='%s', token_provided=%s",
        field_name, original_source, applicant_id, bool(auth_token),
    )

    alt_result = _ALTERNATE_RESULTS.get(field_name, {
        "source": "Generic alternate DB",
        "verified_value": declared_value,
        "match_confidence": 0.50,
        "notes": "No specific alternate source available for this field",
    })

    # Guard: Calls to PAN or Aadhaar services require a valid service token
    source_name = alt_result.get("source", "")
    if "Aadhaar" in source_name or "PAN" in source_name:
        if not auth_token:
            log.warning("Tool [reverify_alternate_source] BLOCKED — missing service token for %s", source_name)
            return {
                "tool": "reverify_alternate_source",
                "success": False,
                "error": f"UNAUTHORIZED: Valid service token required to access {source_name}. The agent cannot call this tool without a valid token.",
                "field_name": field_name,
            }
        if auth_token not in (api_config.pan_service_token, api_config.aadhaar_service_token):
            log.warning("Tool [reverify_alternate_source] REJECTED — invalid service token '%s' for %s", auth_token, source_name)
            return {
                "tool": "reverify_alternate_source",
                "success": False,
                "error": f"UNAUTHORIZED: Invalid service token for {source_name}.",
                "field_name": field_name,
            }

    return {
        "tool": "reverify_alternate_source",
        "field_name": field_name,
        "declared_value": declared_value,
        "original_source": original_source,
        "alternate_source": alt_result["source"],
        "alternate_verified_value": alt_result["verified_value"],
        "match_confidence": alt_result["match_confidence"],
        "notes": alt_result["notes"],
        "success": True,
    }

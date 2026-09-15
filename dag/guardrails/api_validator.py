"""
Guard 5 — API parameter validation.

Deterministic validation of parameters before hitting mocked
PAN / GST / Bureau / CERSAI verification APIs.
"""

import re
from app.config.logger import get_logger

log = get_logger(__name__)


class APIValidationError(Exception):
    """Raised when API parameters fail validation."""

    def __init__(self, api_name: str, errors: list[str]):
        self.api_name = api_name
        self.errors = errors
        super().__init__(f"API validation failed for '{api_name}': {'; '.join(errors)}")


def validate_pan(pan_number: str) -> list[str]:
    """Validate PAN number format: [A-Z]{5}[0-9]{4}[A-Z]."""
    errors = []
    if not pan_number:
        errors.append("PAN number is required")
    elif not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan_number):
        errors.append(f"Invalid PAN format: '{pan_number}' — expected ABCDE1234F pattern")
    return errors


def validate_gstin(gstin: str) -> list[str]:
    """Validate GSTIN format: 2-digit state code + PAN + 1 digit + Z + 1 alphanumeric."""
    errors = []
    if not gstin:
        errors.append("GSTIN is required")
    elif not re.match(r"^\d{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$", gstin):
        errors.append(f"Invalid GSTIN format: '{gstin}'")
    return errors


def validate_aadhaar(aadhaar: str) -> list[str]:
    """Validate Aadhaar: 12 digits, not starting with 0 or 1."""
    errors = []
    clean = re.sub(r"\s", "", aadhaar)
    if not clean:
        errors.append("Aadhaar number is required")
    elif not re.match(r"^[2-9]\d{11}$", clean):
        errors.append(f"Invalid Aadhaar format: '{aadhaar}'")
    return errors


def validate_api_params(api_name: str, params: dict) -> None:
    """Validate parameters for a specific verification API.

    Args:
        api_name: One of 'pan', 'gst', 'bureau', 'cersai'.
        params: Dictionary of parameters to validate.

    Raises:
        APIValidationError: If any parameter validation fails.
    """
    errors = []

    if api_name == "pan":
        errors.extend(validate_pan(params.get("pan_number", "")))
        if not params.get("token"):
            errors.append("Service token is required to access PAN API")

    elif api_name == "aadhaar":
        errors.extend(validate_aadhaar(params.get("aadhaar_number", "")))
        if not params.get("token"):
            errors.append("Service token is required to access Aadhaar API")

    elif api_name == "gst":
        errors.extend(validate_gstin(params.get("gst_number", "")))

    elif api_name == "bureau":
        pan_errors = validate_pan(params.get("pan_number", ""))
        errors.extend(pan_errors)
        if params.get("dob") and not re.match(r"^\d{4}-\d{2}-\d{2}$", params["dob"]):
            errors.append(f"Invalid DOB format: '{params['dob']}' — expected YYYY-MM-DD")

    elif api_name == "cersai":
        # CERSAI needs at least one identifier
        has_id = any(params.get(k) for k in ["pan_number", "aadhaar_number", "property_id"])
        if not has_id:
            errors.append("CERSAI check requires at least one identifier (PAN, Aadhaar, or property_id)")

    else:
        errors.append(f"Unknown API: '{api_name}'")

    if errors:
        log.warning("Guard 5 BLOCKED — API validation failed for '%s': %s", api_name, errors)
        raise APIValidationError(api_name, errors)

    log.info("Guard 5 PASSED — API params valid for '%s'", api_name)

"""
Guard 7 — Business rules for field-level cross-check.

Compares extracted document fields against verification source results
and produces a list of Discrepancy objects when mismatches exceed
configured tolerances.
"""

from difflib import SequenceMatcher
from app.config.logger import get_logger
from app.config.app_constants import business_rules_config
from app.models.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from app.models.applicant import ExtractedFields

log = get_logger(__name__)


def _name_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two name strings.

    Normalizes whitespace and casing before comparison.
    """
    if not a or not b:
        return 0.0
    a_norm = " ".join(a.lower().split())
    b_norm = " ".join(b.lower().split())
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _address_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two address strings."""
    if not a or not b:
        return 0.0
    a_norm = " ".join(a.lower().replace(",", " ").replace(".", " ").split())
    b_norm = " ".join(b.lower().replace(",", " ").replace(".", " ").split())
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _income_deviation(declared: float, verified: float) -> float:
    """Calculate the fractional deviation between declared and verified income.

    Returns a value between 0 and 1+ (e.g. 0.25 = 25% deviation).
    """
    if verified == 0:
        return 1.0 if declared > 0 else 0.0
    return abs(declared - verified) / verified


def check_name(
    declared_name: str,
    verified_name: str,
    source: str,
) -> Discrepancy | None:
    """Compare declared name against a verified name from a source."""
    if not verified_name:
        return None
    similarity = _name_similarity(declared_name, verified_name)
    if similarity >= business_rules_config.name_match_threshold:
        log.info("Guard 7 — name match OK (%.2f) against %s", similarity, source)
        return None

    # Determine severity based on how different the names are
    if similarity >= 0.7:
        severity = DiscrepancySeverity.LOW
    elif similarity >= 0.5:
        severity = DiscrepancySeverity.MEDIUM
    else:
        severity = DiscrepancySeverity.HIGH

    return Discrepancy(
        discrepancy_type=DiscrepancyType.NAME_MISMATCH,
        severity=severity,
        field_name="applicant_name",
        declared_value=declared_name,
        verified_value=verified_name,
        source=source,
        details=f"Name similarity {similarity:.2f} below threshold {business_rules_config.name_match_threshold}",
    )


def check_address(
    declared_address: str,
    verified_address: str,
    source: str,
) -> Discrepancy | None:
    """Compare declared address against a verified address."""
    if not verified_address:
        return None
    similarity = _address_similarity(declared_address, verified_address)
    if similarity >= business_rules_config.address_match_threshold:
        log.info("Guard 7 — address match OK (%.2f) against %s", similarity, source)
        return None

    if similarity >= 0.6:
        severity = DiscrepancySeverity.LOW
    elif similarity >= 0.4:
        severity = DiscrepancySeverity.MEDIUM
    else:
        severity = DiscrepancySeverity.HIGH

    return Discrepancy(
        discrepancy_type=DiscrepancyType.ADDRESS_MISMATCH,
        severity=severity,
        field_name="address",
        declared_value=declared_address,
        verified_value=verified_address,
        source=source,
        details=f"Address similarity {similarity:.2f} below threshold {business_rules_config.address_match_threshold}",
    )


def check_income(
    declared_income: float,
    verified_income: float,
    source: str,
) -> Discrepancy | None:
    """Compare declared income against verified income.

    Uses the materiality threshold to determine if the deviation is significant.
    """
    if verified_income == 0 and declared_income == 0:
        return None

    deviation = _income_deviation(declared_income, verified_income)
    if deviation <= business_rules_config.income_materiality_threshold:
        log.info("Guard 7 — income match OK (deviation %.2f) against %s", deviation, source)
        return None

    if deviation <= 0.3:
        severity = DiscrepancySeverity.MEDIUM
    elif deviation <= 0.5:
        severity = DiscrepancySeverity.HIGH
    else:
        severity = DiscrepancySeverity.CRITICAL

    return Discrepancy(
        discrepancy_type=DiscrepancyType.INCOME_MISMATCH,
        severity=severity,
        field_name="annual_income",
        declared_value=str(declared_income),
        verified_value=str(verified_income),
        source=source,
        details=f"Income deviation {deviation:.1%} exceeds materiality threshold {business_rules_config.income_materiality_threshold:.1%}",
    )


def check_dob(
    declared_dob: str,
    verified_dob: str,
    source: str,
) -> Discrepancy | None:
    """Compare declared date of birth against verified DOB."""
    if not verified_dob:
        return None
    if declared_dob.strip() == verified_dob.strip():
        log.info("Guard 7 — DOB match OK against %s", source)
        return None

    return Discrepancy(
        discrepancy_type=DiscrepancyType.DOB_MISMATCH,
        severity=DiscrepancySeverity.HIGH,
        field_name="date_of_birth",
        declared_value=declared_dob,
        verified_value=verified_dob,
        source=source,
        details="Date of birth mismatch — this is an exact-match field",
    )


def run_cross_check(
    extracted: ExtractedFields,
    verification_results: dict,
    declared_income: float,
    declared_name: str,
    declared_address: str,
    declared_dob: str,
) -> list[Discrepancy]:
    """Run all business rule cross-checks and return found discrepancies.

    Args:
        extracted: Fields extracted from applicant documents.
        verification_results: Results from PAN/GST/Bureau/CERSAI mocks.
        declared_income: Self-declared annual income.
        declared_name: Applicant's stated name.
        declared_address: Applicant's stated address.
        declared_dob: Applicant's stated DOB.

    Returns:
        List of Discrepancy objects found.
    """
    discrepancies: list[Discrepancy] = []

    # ── Name checks ──────────────────────────────────────────────────────
    pan_result = verification_results.get("pan", {})
    if pan_result.get("name"):
        d = check_name(declared_name, pan_result["name"], "PAN DB")
        if d:
            discrepancies.append(d)

    gst_result = verification_results.get("gst", {})
    if gst_result.get("business_name"):
        d = check_name(declared_name, gst_result["business_name"], "GST Registry")
        if d:
            discrepancies.append(d)

    # ── DOB checks ───────────────────────────────────────────────────────
    if pan_result.get("dob"):
        d = check_dob(declared_dob, pan_result["dob"], "PAN DB")
        if d:
            discrepancies.append(d)

    # ── Address checks ───────────────────────────────────────────────────
    if gst_result.get("business_address"):
        d = check_address(declared_address, gst_result["business_address"], "GST Registry")
        if d:
            discrepancies.append(d)

    # ── Income checks ────────────────────────────────────────────────────
    bureau_result = verification_results.get("bureau", {})
    if bureau_result.get("income_estimate"):
        d = check_income(declared_income, bureau_result["income_estimate"], "Credit Bureau")
        if d:
            discrepancies.append(d)

    # ── CERSAI flags ─────────────────────────────────────────────────────
    cersai_result = verification_results.get("cersai", {})
    if cersai_result.get("has_existing_charge"):
        discrepancies.append(Discrepancy(
            discrepancy_type=DiscrepancyType.CERSAI_FLAG,
            severity=DiscrepancySeverity.HIGH,
            field_name="property_encumbrance",
            declared_value="no existing charge declared",
            verified_value="existing charge found",
            source="CERSAI",
            details=f"CERSAI reports existing charge: {cersai_result.get('charge_details', 'N/A')}",
        ))

    # ── Verification timeouts ────────────────────────────────────────────
    for api_name, result in verification_results.items():
        if result.get("timed_out"):
            discrepancies.append(Discrepancy(
                discrepancy_type=DiscrepancyType.VERIFICATION_TIMEOUT,
                severity=DiscrepancySeverity.MEDIUM,
                field_name=f"{api_name}_verification",
                declared_value="N/A",
                verified_value="TIMEOUT",
                source=api_name.upper(),
                details=f"{api_name.upper()} verification timed out",
            ))

    if discrepancies:
        log.warning(
            "Guard 7 — %d discrepancy(ies) found: %s",
            len(discrepancies),
            [(d.discrepancy_type.value, d.severity.value) for d in discrepancies],
        )
    else:
        log.info("Guard 7 PASSED — all fields match within tolerance")

    return discrepancies

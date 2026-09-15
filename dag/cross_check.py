"""
DAG Node 3 — Field-level cross-check.

Delegates to Guard 7 (business_rules) to compare extracted fields
against verification results.
"""

from app.models.applicant import LoanApplication, ExtractedFields
from app.models.discrepancy import Discrepancy
from dag.guardrails.business_rules import run_cross_check
from app.config.logger import get_logger

log = get_logger(__name__)


def cross_check_fields(
    application: LoanApplication,
    extracted: ExtractedFields,
    verification_results: dict[str, dict],
) -> list[Discrepancy]:
    """Compare extracted/declared values against verification sources.

    This is a thin wrapper around Guard 7's run_cross_check.

    Args:
        application: The original loan application (source of declared values).
        extracted: Fields extracted from documents.
        verification_results: Results from parallel verification calls.

    Returns:
        List of Discrepancy objects found.
    """
    log.info("DAG cross-check — starting for applicant %s", application.applicant_id)

    discrepancies = run_cross_check(
        extracted=extracted,
        verification_results=verification_results,
        declared_income=application.annual_income,
        declared_name=application.applicant_name,
        declared_address=application.address,
        declared_dob=application.date_of_birth,
    )

    if discrepancies:
        log.info(
            "DAG cross-check — %d discrepancy(ies) found for applicant %s",
            len(discrepancies),
            application.applicant_id,
        )
    else:
        log.info(
            "DAG cross-check — no discrepancies for applicant %s",
            application.applicant_id,
        )

    return discrepancies

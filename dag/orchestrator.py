"""
DAG pipeline — orchestrates extraction → verification → cross-check.

This is the deterministic pipeline that runs before the agent.
If discrepancies are found, they're passed to the agent loop.
"""

import asyncio
from app.models.applicant import LoanApplication, ExtractedFields
from app.models.discrepancy import Discrepancy
from dag.extraction import extract_fields
from dag.verification import run_parallel_verification
from dag.cross_check import cross_check_fields
from app.config.logger import get_logger

log = get_logger(__name__)


class DAGResult:
    """Result from the DAG pipeline."""

    def __init__(
        self,
        extracted: ExtractedFields,
        verification_results: dict[str, dict],
        discrepancies: list[Discrepancy],
    ):
        self.extracted = extracted
        self.verification_results = verification_results
        self.discrepancies = discrepancies

    @property
    def has_discrepancies(self) -> bool:
        return len(self.discrepancies) > 0


async def run_dag(application: LoanApplication) -> DAGResult:
    """Run the full DAG pipeline: extract → verify → cross-check.

    Args:
        application: Validated loan application.

    Returns:
        DAGResult with extracted fields, verification results, and discrepancies.
    """
    log.info("═══ DAG PIPELINE START — applicant %s ═══", application.applicant_id)

    # Step 1: Extract fields from documents
    extracted = extract_fields(application)

    # Step 2: Run parallel verification calls
    verification_results = await run_parallel_verification(
        extracted=extracted,
        dob=application.date_of_birth,
    )

    # Step 3: Cross-check fields
    discrepancies = cross_check_fields(
        application=application,
        extracted=extracted,
        verification_results=verification_results,
    )

    log.info(
        "═══ DAG PIPELINE COMPLETE — applicant %s — %d discrepancy(ies) ═══",
        application.applicant_id,
        len(discrepancies),
    )

    return DAGResult(
        extracted=extracted,
        verification_results=verification_results,
        discrepancies=discrepancies,
    )

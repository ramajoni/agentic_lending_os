"""
Verification service orchestrating DAG verification and LangGraph investigation agent.
"""

from typing import Any
from dag.orchestrator import run_dag
from agent.verification.graph import run_investigation
from app.repository.application_repo import ApplicationRepository
from app.schema.response_formatter import (
    format_investigation_response,
    format_no_discrepancy_response,
)
from app.config.logger import get_logger

log = get_logger(__name__)


class VerificationService:
    """Service executing deterministic verification DAG and agent reasoning."""

    @staticmethod
    async def process_verification(application) -> dict:
        """Run the complete lending verification pipeline:
        1. Deterministic DAG (extraction, verification, cross-check)
        2. Agent investigation (if discrepancies found)
        3. Response formatting & redaction
        """
        applicant_id = application.applicant_id
        applicant_name = application.applicant_name
        app_dict = application.model_dump()

        log.info("Processing verification for %s (%s)", applicant_id, applicant_name)

        # 1. Run Deterministic DAG
        dag_result = await run_dag(application)
        extracted_dict = dag_result.extracted.model_dump()
        discrepancy_dicts = [d.model_dump() for d in dag_result.discrepancies]

        # Save DAG results to repository
        ApplicationRepository.save_dag_results(
            applicant_id=applicant_id,
            extracted=extracted_dict,
            verification_results=dag_result.verification_results,
            discrepancies=discrepancy_dicts,
            has_discrepancies=dag_result.has_discrepancies,
        )

        # 2. Branch: Discrepancies vs Clean
        if dag_result.has_discrepancies:
            log.info(
                "DAG found %d discrepancies for %s — invoking LangGraph investigation agent",
                len(dag_result.discrepancies),
                applicant_id,
            )
            final_agent_state = run_investigation(
                applicant_id=applicant_id,
                discrepancies=discrepancy_dicts,
            )

            # Save agent judgment to repository
            ApplicationRepository.save_agent_judgment(
                applicant_id=applicant_id,
                final_state=final_agent_state,
            )

            # Format investigation response (applies Guards 3 & 8)
            return format_investigation_response(final_agent_state)
        else:
            log.info("DAG passed with zero discrepancies for %s — auto-cleared", applicant_id)
            return format_no_discrepancy_response(
                applicant_id=applicant_id,
                extracted_data=extracted_dict,
                verification_results=dag_result.verification_results,
            )


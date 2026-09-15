"""
Customer controller — handles loan application submission and status tracking.
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.application_state import (
    CustomerApplyRequest,
    CustomerApplicationResponse,
    CustomerStatusResponse,
    ApplicationState,
)
from app.models.api_schemas import ErrorResponse
from app.shared.guardrails.injection_scanner import scan_fields
from dag.orchestrator import run_dag
from agent.verification.graph import run_investigation
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/customer", tags=["customer"])


@router.post("/apply")
async def apply_for_loan(payload: CustomerApplyRequest):
    """Customer endpoint to apply for a loan.

    Runs automated DAG and Agent checks, saves factual dossier to SQLite,
    and places the application in 'pending_l1_review' for human underwriter approval.
    """
    try:
        application = payload.application
        applicant_id = application.applicant_id
        applicant_name = application.applicant_name
        app_dict = application.model_dump()

        log.info("Customer application submitted: %s (%s)", applicant_id, applicant_name)

        # ── Guard 2: Injection scan ──────────────────────────────────────────
        injection_violations = scan_fields(app_dict)
        if injection_violations:
            log.warning("Customer application BLOCKED by Guard 2: %s", injection_violations)
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error_code="INJECTION_DETECTED",
                    error_message="Potential injection attack detected in submitted application.",
                    details={"violations": injection_violations},
                ).model_dump(),
            )

        # ── Persist initial application record in SQLite ─────────────────────
        ApplicationRepository.save_application(
            applicant_id=applicant_id,
            applicant_name=applicant_name,
            payload=app_dict,
            initial_state=ApplicationState.PENDING_L1_REVIEW.value,
        )
        ApplicationRepository.record_audit(
            applicant_id=applicant_id,
            actor_type="customer",
            actor_id=applicant_id,
            action="APPLICATION_SUBMITTED",
            to_state=ApplicationState.PENDING_L1_REVIEW.value,
            notes="Customer submitted loan application.",
        )

        # ── Step 1: Run Deterministic DAG ────────────────────────────────────
        dag_result = await run_dag(application)
        extracted_dict = dag_result.extracted.model_dump()
        discrepancy_dicts = [d.model_dump() for d in dag_result.discrepancies]

        ApplicationRepository.save_dag_results(
            applicant_id=applicant_id,
            extracted=extracted_dict,
            verification_results=dag_result.verification_results,
            discrepancies=discrepancy_dicts,
            has_discrepancies=dag_result.has_discrepancies,
        )

        # ── Step 2: Run Agent Investigation if discrepancies exist ──────────
        if dag_result.has_discrepancies:
            log.info("Discrepancies found (%d) — invoking agent investigation", len(discrepancy_dicts))
            final_state = await asyncio.get_event_loop().run_in_executor(
                None,
                run_investigation,
                applicant_id,
                discrepancy_dicts,
            )
            ApplicationRepository.save_agent_judgment(applicant_id, final_state)
            ApplicationRepository.record_audit(
                applicant_id=applicant_id,
                actor_type="agent",
                actor_id=final_state.get("agent_id", "discrepancy_investigation_agent"),
                action="AGENT_INVESTIGATION_COMPLETED",
                notes=f"Agent completed investigation with confidence {final_state.get('confidence')}. Action: {final_state.get('terminal_action')}",
            )
        else:
            log.info("Zero discrepancies found — clean factual dossier ready for L1 review.")
            ApplicationRepository.record_audit(
                applicant_id=applicant_id,
                actor_type="system",
                actor_id="dag_engine",
                action="DAG_ALL_CHECKS_PASSED",
                notes="All verification checks passed with 0 discrepancies.",
            )

        now = datetime.now(timezone.utc).isoformat()
        return CustomerApplicationResponse(
            application_id=applicant_id,
            status=ApplicationState.PENDING_L1_REVIEW,
            message="Your application has been received and is queued for underwriting review by our team.",
            submitted_at=now,
        )

    except Exception as e:
        log.error("Unhandled error in customer application: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                error_message="An internal error occurred while processing your application.",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.get("/applications/{applicant_id}/status")
async def get_application_status(applicant_id: str):
    """Customer endpoint to query application status."""
    app_record = ApplicationRepository.get_application(applicant_id)
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")

    state_messages = {
        ApplicationState.PENDING_L1_REVIEW.value: "Your application is currently under review by our underwriting team.",
        ApplicationState.L2_REVIEW.value: "Your application is undergoing secondary review by our senior underwriting committee.",
        ApplicationState.APPROVED.value: "Congratulations! Your loan application has been approved.",
        ApplicationState.REJECTED.value: "We regret to inform you that your application does not meet our lending criteria.",
        ApplicationState.SUBMITTED.value: "Your application has been received.",
    }

    current_state = app_record["current_state"]
    message = state_messages.get(current_state, "Your application is being processed.")

    return CustomerStatusResponse(
        application_id=applicant_id,
        status=ApplicationState(current_state),
        submitted_at=app_record["created_at"],
        updated_at=app_record["updated_at"],
        message=message,
    )

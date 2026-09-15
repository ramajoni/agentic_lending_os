"""
Verification controller — route handlers for the lending pipeline.

Thin orchestration layer: validate → DAG → agent → format response.
No business logic lives here.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models.api_schemas import VerificationRequest, ErrorResponse
from app.api.guardrails.input_validator import validate_input, InputValidationError
from app.shared.guardrails.injection_scanner import scan_fields, InjectionDetectedError
from app.shared.guardrails.pii_redactor import redact_for_logging
from dag.orchestrator import run_dag
from agent.verification.graph import run_investigation
from app.api.schemas.response_formatter import format_investigation_response, format_no_discrepancy_response
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["verification"])


@router.post("/verify")
async def verify_application(payload: VerificationRequest):
    """Main entry point — verify a loan application.

    Pipeline: Guard 1 → Guard 2 → DAG → Agent (if discrepancies) → Guard 8 + Guard 3 → Response
    """
    try:
        log.info("POST /api/v1/verify — received request")

        # ── Guard 1: Input/schema validation ────────────────────────────
        application = payload.application
        log.info(
            "Guard 1 PASSED — input validation OK for applicant %s (%s)",
            application.applicant_id,
            application.applicant_name,
        )

        # ── Guard 2: Injection scan on free-text fields ──────────────────
        app_dict = application.model_dump()
        injection_violations = scan_fields(app_dict)
        if injection_violations:
            log.warning(
                "Guard 2 BLOCKED — rejected request due to injection: %s",
                [v["field"] for v in injection_violations],
            )
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error_code="INJECTION_DETECTED",
                    error_message="Potential injection attack (prompt or SQL/command injection) detected in input fields",
                    details={"violations": injection_violations},
                ).model_dump(),
            )

        # ── DAG: extraction → verification → cross-check ────────────────
        dag_result = await run_dag(application)
        extracted_dict = dag_result.extracted.model_dump()
        discrepancy_dicts = [d.model_dump() for d in dag_result.discrepancies]

        # Persist base application and DAG findings in SQLite
        from app.db.repository import ApplicationRepository
        ApplicationRepository.save_application(
            applicant_id=application.applicant_id,
            applicant_name=application.applicant_name,
            payload=app_dict,
            initial_state="pending_l1_review",
        )
        ApplicationRepository.save_dag_results(
            applicant_id=application.applicant_id,
            extracted=extracted_dict,
            verification_results=dag_result.verification_results,
            discrepancies=discrepancy_dicts,
            has_discrepancies=dag_result.has_discrepancies,
        )

        # ── If no discrepancies, return clean result ─────────────────────
        if not dag_result.has_discrepancies:
            log.info("No discrepancies found — returning clean result")
            ApplicationRepository.record_audit(
                applicant_id=application.applicant_id,
                actor_type="system",
                actor_id="dag_engine",
                action="DAG_ALL_CHECKS_PASSED",
                to_state="pending_l1_review",
                notes="All verification checks passed with 0 discrepancies.",
            )
            response = format_no_discrepancy_response(application.applicant_id)
            return JSONResponse(status_code=200, content=response)

        # ── Agent: investigation loop ────────────────────────────────────
        log.info(
            "Discrepancies found (%d) — starting agent investigation",
            len(dag_result.discrepancies),
        )

        # Run the synchronous graph in a thread pool to not block the event loop
        final_state = await asyncio.get_event_loop().run_in_executor(
            None,
            run_investigation,
            application.applicant_id,
            discrepancy_dicts,
        )

        # Persist agent findings & audit trail
        ApplicationRepository.save_agent_judgment(application.applicant_id, final_state)
        ApplicationRepository.record_audit(
            applicant_id=application.applicant_id,
            actor_type="agent",
            actor_id=final_state.get("agent_id", "discrepancy_investigation_agent"),
            action="AGENT_INVESTIGATION_COMPLETED",
            to_state="pending_l1_review",
            notes=f"Agent completed investigation: {final_state.get('rationale', '')[:100]}",
        )

        # ── Format response (Guards 3, 8) ────────────────────────────────
        response = format_investigation_response(final_state)

        status_code = 200 if response["status"] == "completed" else 202
        return JSONResponse(status_code=status_code, content=response)

    except Exception as e:
        log.error("Unhandled error in verify_application: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                error_message="An internal error occurred during verification",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "guardrail_poc"}

"""
Unified Applications controller — resource-oriented API with role-based data projection.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.models.application_state import (
    CustomerApplyRequest,
    CustomerApplicationResponse,
    CustomerStatusResponse,
    ApplicationState,
    CaseDossierResponse,
    CaseDrillDownResponse,
    ReviewDecisionResponse,
)
from app.models.api_schemas import ErrorResponse
from app.auth.dependencies import get_current_user, require_roles, AuthenticatedUser
from app.shared.guardrails.injection_scanner import scan_fields
from dag.orchestrator import run_dag
from agent.verification.graph import run_investigation
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


class UnifiedDecisionRequest(BaseModel):
    """Decision payload adaptable to L1 or L2 reviewer permissions."""

    decision: str = Field(..., description="Decision: approved | l2_review | rejected")
    notes: Optional[str] = Field(None, description="Notes for L1 decision")
    justification: Optional[str] = Field(None, description="Mandatory detailed justification for L2 decision")


# ── 1. Submit Application (Customer) ─────────────────────────────────────────

@router.post("", response_model=CustomerApplicationResponse)
async def submit_application(
    payload: CustomerApplyRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["customer"])),
):
    """Submit a loan application. Restricted to customers.

    Runs automated DAG checks, agent investigation (if discrepancies exist),
    persists full dossier to SQLite, and queues case in 'pending_l1_review'.
    """
    try:
        application = payload.application
        applicant_id = application.applicant_id
        applicant_name = application.applicant_name
        app_dict = application.model_dump()

        log.info("Application submitted: %s (%s) by user %s", applicant_id, applicant_name, current_user.username)

        # Guard 2: Injection Scan
        injection_violations = scan_fields(app_dict)
        if injection_violations:
            log.warning("Application %s BLOCKED by Guard 2: %s", applicant_id, injection_violations)
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error_code="INJECTION_DETECTED",
                    error_message="Potential injection attack detected in submitted application.",
                    details={"violations": injection_violations},
                ).model_dump(),
            )

        # Persist to SQLite
        ApplicationRepository.save_application(
            applicant_id=applicant_id,
            applicant_name=applicant_name,
            payload=app_dict,
            initial_state=ApplicationState.PENDING_L1_REVIEW.value,
        )
        ApplicationRepository.record_audit(
            applicant_id=applicant_id,
            actor_type="customer",
            actor_id=current_user.user_id,
            action="APPLICATION_SUBMITTED",
            to_state=ApplicationState.PENDING_L1_REVIEW.value,
            notes=f"Customer {current_user.username} submitted application.",
        )

        # Step 1: Deterministic DAG
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

        # Step 2: Agent Investigation if discrepancies exist
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
                notes=f"Agent investigation completed: {final_state.get('terminal_action')}",
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
        log.error("Error processing application: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                error_message="An internal error occurred while processing application.",
                details={"error": str(e)},
            ).model_dump(),
        )


# ── 2. List Applications / Queues (Role-Filtered) ───────────────────────────

@router.get("", response_model=list[dict])
async def list_applications(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve applications based on the authenticated user's role.

    - Customer: returns customer's own applications.
    - L1 Reviewer: returns 'pending_l1_review' queue.
    - L2 Reviewer: returns 'l2_review' queue.
    - Manager: returns all applications across all states.
    """
    role = current_user.role

    if role == "customer":
        # Returns applications belonging to customer or general list
        apps = ApplicationRepository.list_all_applications()
        # Filter for customer or return sanitized summaries
        return [
            {
                "application_id": a["applicant_id"],
                "status": a["current_state"],
                "created_at": a["created_at"],
            }
            for a in apps
        ]

    elif role == "l1_reviewer":
        return ApplicationRepository.list_queue(state=ApplicationState.PENDING_L1_REVIEW.value)

    elif role == "l2_reviewer":
        return ApplicationRepository.list_queue(state=ApplicationState.L2_REVIEW.value)

    elif role == "manager":
        return ApplicationRepository.list_all_applications()

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown role.")


# ── 3. View Case Details (Role-Projected View) ────────────────────────────────

@router.get("/{applicant_id}")
async def get_application_details(
    applicant_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve case details projected based on the user's role.

    - Customer: sanitized customer view (status, timestamps, message; hides agent reasoning/fraud hits).
    - L1 / L2 Reviewer: complete factual dossier checked by the agent.
    - Manager: complete factual dossier + full chronological audit drill-down.
    """
    dossier = ApplicationRepository.get_dossier(applicant_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")

    role = current_user.role

    # ── Projection for Customer: Sanitized Status Only ──────────────────────
    if role == "customer":
        state_messages = {
            ApplicationState.PENDING_L1_REVIEW.value: "Your application is currently under review by our underwriting team.",
            ApplicationState.L2_REVIEW.value: "Your application is undergoing secondary review by our senior underwriting committee.",
            ApplicationState.APPROVED.value: "Congratulations! Your loan application has been approved.",
            ApplicationState.REJECTED.value: "We regret to inform you that your application does not meet our lending criteria.",
        }
        current_state = dossier["current_state"]
        return CustomerStatusResponse(
            application_id=applicant_id,
            status=ApplicationState(current_state),
            submitted_at=dossier["created_at"],
            updated_at=dossier["updated_at"],
            message=state_messages.get(current_state, "Your application is being processed."),
        )

    # ── Projection for Reviewers: Full Factual Dossier ──────────────────────
    if role in ("l1_reviewer", "l2_reviewer"):
        return dossier

    # ── Projection for Manager: Dossier + Chronological Drill-Down ───────────
    if role == "manager":
        drilldown = ApplicationRepository.get_case_drilldown(applicant_id)
        return {
            "dossier": dossier,
            "drilldown": drilldown,
        }

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized role projection.")


# ── 4. Reviewer Decision Gate ────────────────────────────────────────────────

@router.post("/{applicant_id}/decision", response_model=ReviewDecisionResponse)
async def submit_case_decision(
    applicant_id: str,
    payload: UnifiedDecisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Apply an underwriting decision. Validates authority by role.

    - Customer: 403 Forbidden.
    - L1 Reviewer: can move to 'approved', 'l2_review', or 'rejected'.
    - L2 Reviewer: can move to 'approved' or 'rejected' with mandatory justification.
    """
    role = current_user.role
    decision = payload.decision.lower()

    if role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Customers are not permitted to submit underwriting decisions.",
        )

    # L1 Reviewer Action
    if role == "l1_reviewer":
        if decision not in ("approved", "l2_review", "rejected"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L1 Reviewer can only transition to: 'approved', 'l2_review', or 'rejected'.",
            )
        notes = payload.notes or payload.justification or "Decision recorded by L1 Reviewer."
        try:
            result = ApplicationRepository.record_l1_decision(
                applicant_id=applicant_id,
                reviewer_id=current_user.user_id,
                decision=decision,
                notes=notes,
            )
            return ReviewDecisionResponse(
                application_id=result["application_id"],
                previous_state=ApplicationState(result["previous_state"]),
                current_state=ApplicationState(result["current_state"]),
                decision=result["decision"],
                reviewer_id=result["reviewer_id"],
                notes_or_justification=result["notes_or_justification"],
                timestamp=result["timestamp"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # L2 Reviewer Action
    if role in ("l2_reviewer", "manager"):
        if decision not in ("approved", "rejected"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L2 Senior Reviewer can only issue terminal decisions: 'approved' or 'rejected'.",
            )
        justification = payload.justification or payload.notes
        if not justification or len(justification.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A detailed justification of at least 10 characters is mandatory for L2 decisioning.",
            )
        try:
            result = ApplicationRepository.record_l2_decision(
                applicant_id=applicant_id,
                reviewer_id=current_user.user_id,
                decision=decision,
                justification=justification.strip(),
            )
            return ReviewDecisionResponse(
                application_id=result["application_id"],
                previous_state=ApplicationState(result["previous_state"]),
                current_state=ApplicationState(result["current_state"]),
                decision=result["decision"],
                reviewer_id=result["reviewer_id"],
                notes_or_justification=result["notes_or_justification"],
                timestamp=result["timestamp"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized role.")


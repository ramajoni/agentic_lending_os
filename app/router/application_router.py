"""
FastAPI router for application lifecycle, customer submissions, and reviewer decisions.
"""

from typing import Optional, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.models.application_state import (
    CustomerApplyRequest,
    CustomerApplicationResponse,
    L1ReviewDecisionRequest,
    L2ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from app.controller.application_controller import ApplicationController
from app.utils.auth_deps import get_current_user, require_roles, AuthenticatedUser

router = APIRouter(tags=["applications"])


class UnifiedDecisionRequest(BaseModel):
    decision: str = Field(..., description="Decision: approved | l2_review | rejected")
    notes: Optional[str] = Field(None, description="Notes for L1 decision")
    justification: Optional[str] = Field(None, description="Mandatory justification for L2 decision")


# ── Unified Resource Endpoints (/applications) ───────────────────────────────

@router.post("/applications", response_model=CustomerApplicationResponse)
async def submit_application(
    payload: CustomerApplyRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["customer"])),
):
    """Submit loan application (restricted to customer role)."""
    return await ApplicationController.submit_application(
        payload=payload,
        actor_id=current_user.user_id,
        actor_username=current_user.username,
    )


@router.get("/applications", response_model=list[dict])
async def list_applications(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve applications based on authenticated user's role."""
    return ApplicationController.list_applications_for_user(current_user)


@router.get("/applications/{applicant_id}")
async def get_application_details(
    applicant_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve case details projected based on the user's role."""
    return ApplicationController.get_application_details_for_user(applicant_id, current_user)


@router.post("/applications/{applicant_id}/decision", response_model=ReviewDecisionResponse)
async def submit_case_decision(
    applicant_id: str,
    payload: UnifiedDecisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Apply an underwriting decision gate validated by role."""
    return ApplicationController.record_unified_decision(
        applicant_id=applicant_id,
        decision=payload.decision,
        notes=payload.notes,
        justification=payload.justification,
        current_user=current_user,
    )


# ── Legacy & Direct Endpoints ───────────────────────────────────────────────

@router.get("/applications/{applicant_id}/status")
async def get_application_status(applicant_id: str):
    """Check application status."""
    return ApplicationController.get_status(applicant_id)


@router.get("/applications/queue/{state}")
async def get_queue(state: str):
    """Get queue items by state."""
    return ApplicationController.list_queue(state)


@router.post("/customer/apply", response_model=CustomerApplicationResponse)
async def customer_apply(payload: CustomerApplyRequest):
    """Customer apply endpoint."""
    return await ApplicationController.submit_application(
        payload=payload,
        actor_id="USR-CUST-DEFAULT",
        actor_username="customer",
    )


@router.get("/customer/applications/{applicant_id}/status")
async def customer_status(applicant_id: str):
    """Customer status endpoint."""
    return ApplicationController.get_status(applicant_id)


@router.get("/reviewer/l1/queue")
@router.get("/reviewer/queue/l1")
async def reviewer_l1_queue():
    """L1 reviewer queue."""
    return ApplicationController.list_queue("pending_l1_review")


@router.get("/reviewer/l2/queue")
@router.get("/reviewer/queue/l2")
async def reviewer_l2_queue():
    """L2 reviewer queue."""
    return ApplicationController.list_queue("l2_review")


@router.get("/reviewer/l1/applications/{applicant_id}")
@router.get("/reviewer/l2/applications/{applicant_id}")
@router.get("/reviewer/dossier/{applicant_id}")
async def reviewer_dossier(applicant_id: str):
    """Reviewer dossier endpoint."""
    return ApplicationController.get_dossier(applicant_id)


@router.post("/reviewer/l1/applications/{applicant_id}/decision")
async def reviewer_l1_decision_path(applicant_id: str, payload: L1ReviewDecisionRequest):
    """L1 reviewer decision endpoint by applicant_id path."""
    return ApplicationController.record_l1_decision(
        applicant_id=applicant_id,
        reviewer_id=payload.reviewer_id,
        decision=payload.decision.value,
        notes=payload.notes,
    )


@router.post("/reviewer/l2/applications/{applicant_id}/decision")
async def reviewer_l2_decision_path(applicant_id: str, payload: L2ReviewDecisionRequest):
    """L2 reviewer decision endpoint by applicant_id path."""
    return ApplicationController.record_l2_decision(
        applicant_id=applicant_id,
        reviewer_id=payload.reviewer_id,
        decision=payload.decision.value,
        justification=payload.justification,
    )

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


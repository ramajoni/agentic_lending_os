"""
Reviewer controller — handles L1 and L2 underwriter review queues and state decisions.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.application_state import (
    ApplicationState,
    L1ReviewDecisionRequest,
    L2ReviewDecisionRequest,
    ReviewDecisionResponse,
    QueueItemSummary,
    CaseDossierResponse,
)
from app.models.api_schemas import ErrorResponse
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/reviewer", tags=["reviewer"])


# ── L1 Reviewer Endpoints ───────────────────────────────────────────────────

@router.get("/l1/queue", response_model=list[QueueItemSummary])
async def get_l1_queue():
    """Retrieve all applications currently pending L1 review."""
    items = ApplicationRepository.list_queue(state=ApplicationState.PENDING_L1_REVIEW.value)
    return items


@router.get("/l1/applications/{applicant_id}", response_model=CaseDossierResponse)
async def get_l1_case_dossier(applicant_id: str):
    """Retrieve the complete factual dossier checked by the agent for L1 review."""
    dossier = ApplicationRepository.get_dossier(applicant_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")
    return dossier


@router.post("/l1/applications/{applicant_id}/decision", response_model=ReviewDecisionResponse)
async def submit_l1_decision(applicant_id: str, payload: L1ReviewDecisionRequest):
    """L1 reviewer evaluates facts and moves case to: approved, l2_review, or rejected."""
    try:
        result = ApplicationRepository.record_l1_decision(
            applicant_id=applicant_id,
            reviewer_id=payload.reviewer_id,
            decision=payload.decision.value,
            notes=payload.notes,
        )
        log.info(
            "L1 Decision applied for %s: %s by %s",
            applicant_id,
            payload.decision.value,
            payload.reviewer_id,
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
    except Exception as e:
        log.error("Error processing L1 decision: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="DECISION_ERROR",
                error_message=f"Failed to record L1 decision: {str(e)}",
            ).model_dump(),
        )


# ── L2 Reviewer Endpoints ───────────────────────────────────────────────────

@router.get("/l2/queue", response_model=list[QueueItemSummary])
async def get_l2_queue():
    """Retrieve all applications escalated to L2 review."""
    items = ApplicationRepository.list_queue(state=ApplicationState.L2_REVIEW.value)
    return items


@router.get("/l2/applications/{applicant_id}", response_model=CaseDossierResponse)
async def get_l2_case_dossier(applicant_id: str):
    """Retrieve complete dossier with L1 escalation history for L2 senior review."""
    dossier = ApplicationRepository.get_dossier(applicant_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")
    return dossier


@router.post("/l2/applications/{applicant_id}/decision", response_model=ReviewDecisionResponse)
async def submit_l2_decision(applicant_id: str, payload: L2ReviewDecisionRequest):
    """L2 senior reviewer issues binding approval or rejection with mandatory justification."""
    try:
        result = ApplicationRepository.record_l2_decision(
            applicant_id=applicant_id,
            reviewer_id=payload.reviewer_id,
            decision=payload.decision.value,
            justification=payload.justification,
        )
        log.info(
            "L2 Decision applied for %s: %s by %s",
            applicant_id,
            payload.decision.value,
            payload.reviewer_id,
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
    except Exception as e:
        log.error("Error processing L2 decision: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="DECISION_ERROR",
                error_message=f"Failed to record L2 decision: {str(e)}",
            ).model_dump(),
        )


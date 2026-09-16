"""
Application controller handling application lifecycle, submissions, queues, and review decisions.
"""

from typing import Optional
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from app.models.application_state import (
    CustomerApplyRequest,
    CustomerApplicationResponse,
    ApplicationState,
)
from app.schema.api_schemas import ErrorResponse
from app.guardrails.injection_scanner import scan_fields
from app.service.application_service import ApplicationService
from app.config.logger import get_logger

log = get_logger(__name__)


class ApplicationController:
    """Controller handling loan application submissions, queues, and decisions."""

    @staticmethod
    async def submit_application(payload: CustomerApplyRequest, actor_id: str, actor_username: str):
        """Handle customer application submission."""
        application = payload.application
        applicant_id = application.applicant_id
        applicant_name = application.applicant_name
        app_dict = application.model_dump()

        log.info("Application submission initiated: %s (%s) by user %s", applicant_id, applicant_name, actor_username)

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

        # Process via ApplicationService
        result = await ApplicationService.create_application(
            application=application,
            actor_id=actor_id,
            actor_username=actor_username,
        )
        return CustomerApplicationResponse(
            application_id=result["application_id"],
            status=result["status"],
            message=result["message"],
        )

    @staticmethod
    def get_status(applicant_id: str) -> dict:
        """Fetch status for applicant."""
        status_info = ApplicationService.get_status(applicant_id)
        if not status_info:
            raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")
        return status_info

    @staticmethod
    def get_dossier(applicant_id: str) -> dict:
        """Fetch full case dossier."""
        dossier = ApplicationService.get_dossier(applicant_id)
        if not dossier:
            raise HTTPException(status_code=404, detail=f"Application '{applicant_id}' not found.")
        return dossier

    @staticmethod
    def list_queue(state: str) -> list[dict]:
        """Fetch queue items for state."""
        return ApplicationService.list_queue(state)

    @staticmethod
    def record_l1_decision(applicant_id: str, reviewer_id: str, decision: str, notes: Optional[str]) -> dict:
        """Process L1 decision."""
        try:
            return ApplicationService.record_l1_decision(
                applicant_id=applicant_id,
                reviewer_id=reviewer_id,
                decision=decision,
                notes=notes or "",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def record_l2_decision(applicant_id: str, reviewer_id: str, decision: str, justification: Optional[str]) -> dict:
        """Process L2 decision with mandatory justification."""
        if not justification or len(justification.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="L2 Committee approval requires mandatory detailed justification (minimum 10 characters).",
            )
        try:
            return ApplicationService.record_l2_decision(
                applicant_id=applicant_id,
                reviewer_id=reviewer_id,
                decision=decision,
                justification=justification,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


"""
Application service managing loan application lifecycle, review workflows, and dossiers.
"""

from typing import Optional
from app.repository.application_repo import ApplicationRepository
from app.models.application_state import ApplicationState
from app.service.verification_service import VerificationService
from app.config.logger import get_logger

log = get_logger(__name__)


class ApplicationService:
    """Service handling loan application state transitions, reviews, and retrieval."""

    @staticmethod
    async def create_application(application, actor_id: str, actor_username: str) -> dict:
        """Create a new loan application, run verification, and record audit trail."""
        applicant_id = application.applicant_id
        applicant_name = application.applicant_name
        app_dict = application.model_dump()

        # 1. Save application in pending_l1_review
        ApplicationRepository.save_application(
            applicant_id=applicant_id,
            applicant_name=applicant_name,
            payload=app_dict,
            initial_state=ApplicationState.PENDING_L1_REVIEW.value,
        )

        ApplicationRepository.record_audit(
            applicant_id=applicant_id,
            actor_type="customer",
            actor_id=actor_id,
            action="APPLICATION_SUBMITTED",
            to_state=ApplicationState.PENDING_L1_REVIEW.value,
            notes=f"Customer {actor_username} submitted application.",
        )

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        # 2. Run verification pipeline
        verification_output = await VerificationService.process_verification(application)

        return {
            "application_id": applicant_id,
            "status": ApplicationState.PENDING_L1_REVIEW,
            "message": f"Application {applicant_id} submitted successfully and queued for underwriting review.",
            "submitted_at": now,
            "verification_output": verification_output,
        }

    @staticmethod
    def get_status(applicant_id: str) -> Optional[dict]:
        """Fetch high-level application status."""
        app = ApplicationRepository.get_application(applicant_id)
        if not app:
            return None

        state = app["current_state"]
        messages = {
            "pending_l1_review": "Application is under review by our underwriting team.",
            "l2_review": "Application is undergoing senior committee review.",
            "approved": "Congratulations! Your loan application has been approved.",
            "rejected": "Your loan application has been declined based on verification criteria.",
        }

        return {
            "application_id": app["applicant_id"],
            "status": state,
            "message": messages.get(state, f"Application status: {state}"),
            "submitted_at": app["created_at"],
            "updated_at": app["updated_at"],
        }

    @staticmethod
    def get_dossier(applicant_id: str) -> Optional[dict]:
        """Fetch full factual dossier for underwriting."""
        return ApplicationRepository.get_dossier(applicant_id)

    @staticmethod
    def list_queue(state: str) -> list[dict]:
        """List queue items by application state."""
        return ApplicationRepository.list_queue(state)

    @staticmethod
    def record_l1_decision(applicant_id: str, reviewer_id: str, decision: str, notes: str) -> dict:
        """Apply L1 decision (approved, l2_review, rejected)."""
        return ApplicationRepository.record_l1_decision(
            applicant_id=applicant_id,
            reviewer_id=reviewer_id,
            decision=decision,
            notes=notes,
        )

    @staticmethod
    def record_l2_decision(applicant_id: str, reviewer_id: str, decision: str, justification: str) -> dict:
        """Apply L2 decision (approved, rejected) with mandatory justification."""
        return ApplicationRepository.record_l2_decision(
            applicant_id=applicant_id,
            reviewer_id=reviewer_id,
            decision=decision,
            justification=justification,
        )

    @staticmethod
    def list_all_applications() -> list[dict]:
        """List all applications across states for manager view."""
        return ApplicationRepository.list_all_applications()

    @staticmethod
    def get_case_drilldown(applicant_id: str) -> Optional[dict]:
        """Fetch chronological audit drill-down for applicant."""
        return ApplicationRepository.get_case_drilldown(applicant_id)


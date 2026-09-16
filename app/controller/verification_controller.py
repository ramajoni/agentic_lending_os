"""
Verification controller orchestrating lending verification pipeline requests.
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from app.schema.api_schemas import VerificationRequest, ErrorResponse
from app.guardrails.injection_scanner import scan_fields
from app.service.verification_service import VerificationService
from app.config.logger import get_logger

log = get_logger(__name__)


class VerificationController:
    """Controller handling /api/v1/verify requests."""

    @staticmethod
    async def verify(payload: VerificationRequest):
        """Execute verification pipeline with injection scan and DAG/agent processing."""
        application = payload.application
        log.info("VerificationController received request for %s (%s)", application.applicant_id, application.applicant_name)

        # Guard 2: Injection scan on input payload
        app_dict = application.model_dump()
        injection_violations = scan_fields(app_dict)
        if injection_violations:
            log.warning("VerificationController: Guard 2 BLOCKED request due to injection: %s", [v["field"] for v in injection_violations])
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error_code="INJECTION_DETECTED",
                    error_message="Potential injection attack (prompt or SQL/command injection) detected in input fields",
                    details={"violations": injection_violations},
                ).model_dump(),
            )

        # Call VerificationService
        result = await VerificationService.process_verification(application)
        return result


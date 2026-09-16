"""
FastAPI router for deterministic verification & agent investigation pipeline.
"""

from fastapi import APIRouter
from app.schema.api_schemas import VerificationRequest
from app.controller.verification_controller import VerificationController

router = APIRouter(tags=["verification"])


@router.post("/verify")
async def verify_application(payload: VerificationRequest):
    """Verify loan application:
    Pipeline: Input validation → Injection scan → DAG → Investigation Agent (if discrepancies) → Response formatting.
    """
    return await VerificationController.verify(payload)


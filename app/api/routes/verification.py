"""
Verification API routes.
"""

from fastapi import APIRouter
from app.api.controllers.verification import router as controller_router

router = APIRouter()
router.include_router(controller_router)

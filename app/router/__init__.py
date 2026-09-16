"""
Router package aggregating all FastAPI sub-routers under api_v1_router.
"""

from fastapi import APIRouter
from app.router.auth_router import router as auth_router
from app.router.application_router import router as application_router
from app.router.analytics_router import router as analytics_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(application_router)
api_v1_router.include_router(analytics_router)

__all__ = [
    "api_v1_router",
    "auth_router",
    "application_router",
    "analytics_router",
]


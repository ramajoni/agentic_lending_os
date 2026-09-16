"""
FastAPI router for analytics, manager reporting, and health checks.
"""

from fastapi import APIRouter, Depends
from app.controller.analytics_controller import AnalyticsController
from app.utils.auth_deps import require_roles, AuthenticatedUser

router = APIRouter(tags=["analytics"])


@router.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "Agentic Lending Guardrails POC"}


# ── Unified Analytics Endpoints (Protected by RBAC) ──────────────────────────

@router.get("/analytics/leaderboard")
async def get_analytics_leaderboard(
    current_user: AuthenticatedUser = Depends(require_roles(["manager", "admin"])),
):
    """Fetch system leaderboard (manager/admin only)."""
    return AnalyticsController.get_leaderboard()


@router.get("/analytics/cases/{applicant_id}/drilldown")
async def get_analytics_case_drilldown(
    applicant_id: str,
    current_user: AuthenticatedUser = Depends(require_roles(["manager", "admin"])),
):
    """Fetch chronological case drilldown (manager/admin only)."""
    return AnalyticsController.get_case_drilldown(applicant_id)


# ── Manager Direct Endpoints ────────────────────────────────────────────────

@router.get("/manager/leaderboard")
async def get_manager_leaderboard():
    """Manager leaderboard alias."""
    return AnalyticsController.get_leaderboard()


@router.get("/manager/cases/{applicant_id}/drilldown")
async def get_manager_case_drilldown(applicant_id: str):
    """Manager case drilldown alias."""
    return AnalyticsController.get_case_drilldown(applicant_id)

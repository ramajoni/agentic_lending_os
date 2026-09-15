"""
Manager controller — provides operational leaderboard metrics and deep case drill-down.
"""

from fastapi import APIRouter, HTTPException
from app.models.application_state import LeaderboardResponse, CaseDrillDownResponse
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/manager", tags=["manager"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_manager_leaderboard():
    """Retrieve operational pipeline statistics and reviewer performance leaderboard."""
    data = ApplicationRepository.get_leaderboard()
    return data


@router.get("/cases/{applicant_id}/drilldown", response_model=CaseDrillDownResponse)
async def get_case_drilldown(applicant_id: str):
    """Retrieve deep chronological step-by-step audit of a case."""
    drilldown = ApplicationRepository.get_case_drilldown(applicant_id)
    if not drilldown:
        raise HTTPException(status_code=404, detail=f"Case '{applicant_id}' not found.")
    return drilldown


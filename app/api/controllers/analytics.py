"""
Analytics controller — manager operational metrics and reviewer leaderboard.
"""

from fastapi import APIRouter, Depends
from app.models.application_state import LeaderboardResponse
from app.auth.dependencies import require_roles
from app.db.repository import ApplicationRepository

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_operational_leaderboard(
    current_user=Depends(require_roles(["manager"])),
):
    """Retrieve operational pipeline statistics and reviewer leaderboard. Restricted to managers."""
    data = ApplicationRepository.get_leaderboard()
    return data


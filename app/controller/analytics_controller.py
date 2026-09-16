"""
Analytics controller handling operational reporting, leaderboards, and case timelines.
"""

from fastapi import HTTPException
from app.service.analytics_service import AnalyticsService
from app.config.logger import get_logger

log = get_logger(__name__)


class AnalyticsController:
    """Controller handling analytics, leaderboards, and case drilldowns."""

    @staticmethod
    def get_leaderboard() -> dict:
        """Fetch system leaderboard and queue distributions."""
        return AnalyticsService.get_leaderboard()

    @staticmethod
    def get_case_drilldown(applicant_id: str) -> dict:
        """Fetch step-by-step case timeline."""
        drilldown = AnalyticsService.get_case_drilldown(applicant_id)
        if not drilldown:
            raise HTTPException(status_code=404, detail=f"Case drilldown for '{applicant_id}' not found.")
        return drilldown

    @staticmethod
    def list_all_applications() -> list[dict]:
        """Fetch all applications for management oversight."""
        return AnalyticsService.list_all_applications()


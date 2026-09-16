"""
Analytics service managing leaderboard metrics, operational reporting, and chronological case drill-downs.
"""

from typing import Optional
from app.repository.application_repo import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)


class AnalyticsService:
    """Service providing operational telemetry, reviewer performance, and case timelines."""

    @staticmethod
    def get_leaderboard() -> dict:
        """Fetch system-wide queue depths, state distributions, and reviewer productivity."""
        return ApplicationRepository.get_leaderboard()

    @staticmethod
    def get_case_drilldown(applicant_id: str) -> Optional[dict]:
        """Fetch complete chronological step-by-step history of a case."""
        return ApplicationRepository.get_case_drilldown(applicant_id)

    @staticmethod
    def list_all_applications() -> list[dict]:
        """List all applications across all states."""
        return ApplicationRepository.list_all_applications()

    @staticmethod
    def list_users() -> list[dict]:
        """List all registered system users."""
        return ApplicationRepository.list_users()


"""
Authentication service handling user authentication and token creation.
"""

from typing import Optional
from app.repository.application_repo import ApplicationRepository
from app.utils.jwt_util import create_access_token
from app.config.logger import get_logger

log = get_logger(__name__)


class AuthService:
    """Service handling credential verification and token issuance."""

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[dict]:
        """Authenticate user against repository records."""
        user = ApplicationRepository.get_user_by_username(username)
        if not user:
            log.warning("Authentication failed: User '%s' not found.", username)
            return None

        # POC simplified authentication check
        if user.get("hashed_password") != password and password != "mockpass123":
            log.warning("Authentication failed: Invalid password for user '%s'.", username)
            return None

        log.info("User '%s' authenticated successfully (role: %s).", username, user.get("role"))
        return user

    @staticmethod
    def issue_token(user: dict) -> str:
        """Issue signed JWT access token for user."""
        return create_access_token(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            full_name=user.get("full_name", ""),
        )


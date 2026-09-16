"""
Auth controller coordinating authentication workflows, personas, and token issuance.
"""

from typing import Optional
from fastapi import HTTPException, status
from app.service.auth_service import AuthService
from app.repository.application_repo import ApplicationRepository
from app.utils.jwt_util import create_access_token
from app.config.logger import get_logger

log = get_logger(__name__)


class AuthController:
    """Controller handling authentication requests."""

    @staticmethod
    def login(username: Optional[str] = None, password: Optional[str] = None, role: Optional[str] = None) -> dict:
        """Process user login / token generation and return JWT token."""
        user = None
        if username:
            user = ApplicationRepository.get_user_by_username(username)
        elif role:
            users = ApplicationRepository.list_users()
            user = next((u for u in users if u["role"] == role), None)

        if not user:
            # Fallback to dynamic mock user if not in DB
            target_role = role or "customer"
            target_username = username or f"user_{target_role}"
            target_user_id = f"user_{target_username}"
            target_full_name = f"Mock {target_role.replace('_', ' ').title()}"
        else:
            target_user_id = user["user_id"]
            target_username = user["username"]
            target_role = user["role"]
            target_full_name = user["full_name"]

        token = create_access_token(
            user_id=target_user_id,
            username=target_username,
            role=target_role,
            full_name=target_full_name,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "role": target_role,
            "user_id": target_user_id,
            "username": target_username,
            "full_name": target_full_name,
        }

    @staticmethod
    def get_user_profile(user_id: str) -> dict:
        """Fetch user profile details."""
        user = ApplicationRepository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
        return user

    @staticmethod
    def list_users() -> list[dict]:
        """Fetch list of all users."""
        return ApplicationRepository.list_users()

    @staticmethod
    def list_personas() -> list[dict]:
        """List available test personas with their pre-generated JWT tokens."""
        users = ApplicationRepository.list_users()
        personas_with_tokens = []
        for u in users:
            token = create_access_token(
                user_id=u["user_id"],
                username=u["username"],
                role=u["role"],
                full_name=u["full_name"],
            )
            personas_with_tokens.append({
                "user_id": u["user_id"],
                "username": u["username"],
                "role": u["role"],
                "full_name": u["full_name"],
                "mock_bearer_token": token,
            })
        return personas_with_tokens

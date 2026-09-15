"""
Authentication controller — mock login, persona directory, and token issuance.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.auth.jwt_handler import create_access_token
from app.auth.dependencies import get_current_user, AuthenticatedUser
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    """Request body for token generation."""

    username: Optional[str] = Field(None, description="Username of persona (e.g. customer_rajesh, reviewer_l1_amit)")
    role: Optional[str] = Field(None, description="Direct role (e.g. customer, l1_reviewer, l2_reviewer, manager)")


class TokenResponse(BaseModel):
    """JWT Token response."""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str
    full_name: str


@router.post("/token", response_model=TokenResponse)
async def generate_mock_token(payload: TokenRequest):
    """Generate a mock JWT token for testing.

    Provide either a username (e.g. customer_rajesh, reviewer_l1_amit)
    or a role (customer, l1_reviewer, l2_reviewer, manager).
    """
    user = None
    if payload.username:
        user = ApplicationRepository.get_user_by_username(payload.username)
    elif payload.role:
        users = ApplicationRepository.list_users()
        user = next((u for u in users if u["role"] == payload.role), None)

    if not user:
        # If user not found in DB, fallback to a dynamic mock user
        role = payload.role or "customer"
        username = payload.username or f"user_{role}"
        user_id = f"user_{username}"
        full_name = f"Mock {role.replace('_', ' ').title()}"
    else:
        user_id = user["user_id"]
        username = user["username"]
        role = user["role"]
        full_name = user["full_name"]

    token = create_access_token(
        user_id=user_id,
        username=username,
        role=role,
        full_name=full_name,
    )

    log.info("Issued mock JWT for user '%s' (role: %s)", username, role)

    return TokenResponse(
        access_token=token,
        user_id=user_id,
        username=username,
        role=role,
        full_name=full_name,
    )


@router.get("/me", response_model=AuthenticatedUser)
async def get_my_profile(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Retrieve currently authenticated user profile and permissions from JWT."""
    return current_user


@router.get("/personas")
async def list_test_personas():
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


"""
FastAPI router for authentication, persona directory, and token issuance.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.controller.auth_controller import AuthController
from app.utils.auth_deps import get_current_user, require_roles, AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    username: Optional[str] = Field(None, description="Username (e.g. customer_rajesh, reviewer_l1_amit)")
    role: Optional[str] = Field(None, description="Role (e.g. customer, l1_reviewer, l2_reviewer, manager)")
    password: Optional[str] = Field(None, description="Password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str
    full_name: str


@router.post("/token", response_model=TokenResponse)
async def generate_mock_token(payload: TokenRequest):
    """Generate a JWT token for testing."""
    return AuthController.login(username=payload.username, role=payload.role, password=payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(payload: TokenRequest):
    """Authenticate and receive a JWT token."""
    return AuthController.login(username=payload.username, role=payload.role, password=payload.password)


@router.get("/me", response_model=AuthenticatedUser)
async def me(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Fetch profile of currently authenticated user."""
    return current_user


@router.get("/personas")
async def list_personas():
    """List available test personas with pre-generated JWT tokens."""
    return AuthController.list_personas()


@router.get("/users")
async def list_users(current_user: AuthenticatedUser = Depends(require_roles(["admin", "manager"]))):
    """List all registered users."""
    return AuthController.list_users()

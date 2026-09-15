"""
FastAPI authentication and RBAC dependencies.
"""

from typing import Optional, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.auth.jwt_handler import decode_access_token
from app.db.repository import ApplicationRepository
from app.config.logger import get_logger

log = get_logger(__name__)

security = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """User profile extracted from validated JWT token."""

    user_id: str
    username: str
    role: str
    full_name: str = ""


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthenticatedUser:
    """Validate Bearer JWT and return authenticated user details."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")
    full_name = payload.get("full_name", "")

    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload.",
        )

    return AuthenticatedUser(
        user_id=user_id,
        username=username or user_id,
        role=role,
        full_name=full_name,
    )


def require_roles(allowed_roles: list[str]) -> Callable:
    """Dependency that enforces Role-Based Access Control (RBAC)."""

    def role_checker(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            log.warning(
                "Access DENIED for user '%s' (role: '%s'). Required: %s",
                current_user.username,
                current_user.role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Role '{current_user.role}' is not authorized to access this resource. Allowed: {allowed_roles}",
            )
        return current_user

    return role_checker


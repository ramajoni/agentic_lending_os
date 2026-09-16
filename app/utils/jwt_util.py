"""
JWT authentication utility using PyJWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from app.config.logger import get_logger

log = get_logger(__name__)

SECRET_KEY = "guardrail_poc_super_secret_jwt_key_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    full_name: str = "",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT token containing user identity and role."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": user_id,
        "username": username,
        "role": role,
        "full_name": full_name,
        "iat": now,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid authentication token: {str(e)}")


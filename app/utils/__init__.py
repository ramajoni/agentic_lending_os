"""
Utilities package for database connection, JWT handling, authentication dependencies, etc.
"""

from app.utils.db_util import get_db_connection, init_db, get_db_path
from app.utils.jwt_util import create_access_token, decode_access_token
from app.utils.auth_deps import get_current_user, require_roles, AuthenticatedUser

__all__ = [
    "get_db_connection",
    "init_db",
    "get_db_path",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "require_roles",
    "AuthenticatedUser",
]


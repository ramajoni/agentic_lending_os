"""
Backward compatibility bridge. Re-exports from app.schema.api_schemas.
"""

from app.schema.api_schemas import (
    VerificationRequest,
    VerificationResponse,
    ErrorResponse,
)

__all__ = [
    "VerificationRequest",
    "VerificationResponse",
    "ErrorResponse",
]

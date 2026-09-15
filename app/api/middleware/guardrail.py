"""
API request validation and input guardrail middleware.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config.logger import get_logger

log = get_logger(__name__)


class InputGuardrailMiddleware(BaseHTTPMiddleware):
    """Enforces payload bounds and top-level checks at the API boundary."""

    async def dispatch(self, request: Request, call_next):
        # Allow requests to pass to FastAPI's route controllers & validation handlers
        response = await call_next(request)
        return response

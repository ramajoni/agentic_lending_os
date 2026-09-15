"""
Agentic Lending Guardrails POC — FastAPI application entry point.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
# from app.api.routes.verification import router as verification_router
from app.api.controllers.auth import router as auth_router
from app.api.controllers.applications import router as applications_router
from app.api.controllers.analytics import router as analytics_router
# from app.api.controllers.customer import router as customer_router
# from app.api.controllers.reviewer import router as reviewer_router
from app.api.controllers.manager import router as manager_router
from app.api.middleware.guardrail import InputGuardrailMiddleware
from app.models.api_schemas import ErrorResponse
from app.config.logger import setup_logging, get_logger
# from app.utils.openobserver_util import OpenObserver
from app.config.app_constants import openobserver_config

# Initialize logging and SQLite database on startup
setup_logging()
init_db()
log = get_logger(__name__)

# try:
#     openobserver_obj = OpenObserver(
#         username=openobserver_config.username,
#         password=openobserver_config.password,
#         host=openobserver_config.host,
#         port=openobserver_config.port,
#     )
#     # Background log ping
#     openobserver_obj.ingest_log(data={"file_name": "main.py", "msg": "service_started"})
# except Exception as e:
#     log.warning("OpenObserver ping failed: %s", e)

app = FastAPI(
    title="Agentic Lending Guardrails POC",
    description=(
        "A discrepancy investigation agent with 10 guardrails, "
        "sitting downstream of a deterministic document verification DAG. "
        "Supports unified resource-centric API with JWT authentication and role-based data projection."
    ),
    version="0.3.0",
)

# CORS — permissive for POC
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(InputGuardrailMiddleware)

# Register routes
# app.include_router(verification_router)
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(analytics_router)
# app.include_router(customer_router)
# app.include_router(reviewer_router)
app.include_router(manager_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Guard 1 — log and format schema validation errors."""
    log.warning("Guard 1 BLOCKED — input schema validation failed: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code="INPUT_VALIDATION_FAILED",
            error_message="Guard 1: Input payload failed schema validation",
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.get("/")
async def root():
    return {
        "service": "Agentic Lending Guardrails POC",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)

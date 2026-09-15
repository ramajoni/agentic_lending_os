"""
Application configuration loaded from environment variables via pydantic-settings.

All configurable values live here — no other module reads os.environ directly.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class DAGConfig(BaseSettings):
    """Configuration for the deterministic document verification DAG."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    verification_timeout_seconds: int = Field(default=10, alias="VERIFICATION_TIMEOUT_SECONDS")
    max_parallel_calls: int = Field(default=4, alias="MAX_PARALLEL_CALLS")


class AgentConfig(BaseSettings):
    """Configuration for the LangGraph investigation agent."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    max_iterations: int = Field(default=5, alias="MAX_ITERATIONS")
    confidence_threshold: float = Field(default=0.85, alias="CONFIDENCE_THRESHOLD")
    allowlisted_tools_raw: str = Field(
        default="reverify_alternate_source,verify_pan,verify_aadhaar,request_additional_document,query_historical_cases,check_fraud_watchlist,escalate_to_human,auto_clear",
        alias="ALLOWLISTED_TOOLS",
    )
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model_name: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct", alias="GROQ_MODEL_NAME"
    )

    @property
    def allowlisted_tools(self) -> list[str]:
        """Parse the comma-separated tool list into a Python list."""
        return [t.strip() for t in self.allowlisted_tools_raw.split(",") if t.strip()]


class GuardrailConfig(BaseSettings):
    """Configuration for guardrail switches and thresholds."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    pii_redaction_enabled: bool = Field(default=True, alias="PII_REDACTION_ENABLED")
    injection_scan_enabled: bool = Field(default=True, alias="INJECTION_SCAN_ENABLED")
    presidio_enabled: bool = Field(default=True, alias="PRESIDIO_ENABLED")
    prompt_guard_enabled: bool = Field(default=True, alias="PROMPT_GUARD_ENABLED")
    prompt_guard_model: str = Field(
        default="meta-llama/Llama-Prompt-Guard-2-22M", alias="PROMPT_GUARD_MODEL"
    )
    hf_token: str = Field(default="", alias="HF_TOKEN")
    prompt_guard_threshold: float = Field(default=0.5, alias="PROMPT_GUARD_THRESHOLD")


class BusinessRulesConfig(BaseSettings):
    """Thresholds for field-level cross-check business rules (Guard 7)."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    name_match_threshold: float = Field(default=0.85, alias="NAME_MATCH_THRESHOLD")
    address_match_threshold: float = Field(default=0.75, alias="ADDRESS_MATCH_THRESHOLD")
    income_materiality_threshold: float = Field(default=0.20, alias="INCOME_MATERIALITY_THRESHOLD")


class APIConfig(BaseSettings):
    """Configuration for the FastAPI layer."""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    request_timeout_seconds: int = Field(default=30, alias="REQUEST_TIMEOUT_SECONDS")
    max_payload_size_kb: int = Field(default=512, alias="MAX_PAYLOAD_SIZE_KB")
    pan_service_token: str = Field(default="pan_secure_token_2026", alias="PAN_SERVICE_TOKEN")
    aadhaar_service_token: str = Field(default="aadhaar_secure_token_2026", alias="AADHAAR_SERVICE_TOKEN")
    sqlite_db_path: str = Field(default="./data/guardrail_poc.db", alias="SQLITE_DB_PATH")

class OpenObserverConfig(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    host : str = Field(default="http://localhost" ,alias="OPENOB_HOST")
    port: int = Field(default=5080, alias="OPENOB_PORT")
    username: str = Field( alias="OPENOB_USERNAME")
    password: str = Field( alias="OPENOB_PASSWORD")

# ── Singleton instances (import these, don't re-instantiate) ─────────────────

dag_config = DAGConfig()
agent_config = AgentConfig()
guardrail_config = GuardrailConfig()
business_rules_config = BusinessRulesConfig()
api_config = APIConfig()
openobserver_config = OpenObserverConfig()

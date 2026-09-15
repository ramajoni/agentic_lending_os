"""
Discrepancy models.

Represents mismatches found during the DAG's field-level cross-check,
which feed into the agent's investigation loop.
"""

from pydantic import BaseModel, Field
from enum import Enum


class DiscrepancySeverity(str, Enum):
    """Severity classification for a discrepancy."""

    LOW = "low"         # Minor — e.g. spelling variation
    MEDIUM = "medium"   # Noteworthy — e.g. address mismatch
    HIGH = "high"       # Material — e.g. significant income gap
    CRITICAL = "critical"  # Potential fraud signal


class DiscrepancyType(str, Enum):
    """Category of discrepancy found."""

    NAME_MISMATCH = "name_mismatch"
    DOB_MISMATCH = "dob_mismatch"
    ADDRESS_MISMATCH = "address_mismatch"
    INCOME_MISMATCH = "income_mismatch"
    GST_MISMATCH = "gst_mismatch"
    PAN_MISMATCH = "pan_mismatch"
    CERSAI_FLAG = "cersai_flag"
    VERIFICATION_TIMEOUT = "verification_timeout"


class Discrepancy(BaseModel):
    """A single discrepancy found during field-level cross-check."""

    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    field_name: str = Field(..., description="The field where the mismatch was found")
    declared_value: str = Field(..., description="Value from applicant's submission")
    verified_value: str = Field(..., description="Value from verification source")
    source: str = Field(..., description="Verification source (e.g., 'PAN DB', 'Bureau')")
    details: str = Field(default="", description="Human-readable description of the discrepancy")

"""
Applicant and document models.

Represents the loan application payload and the fields extracted
from submitted documents.
"""

from pydantic import BaseModel, Field
from enum import Enum


class DocumentType(str, Enum):
    """Types of documents that can be submitted with a loan application."""

    PAN_CARD = "pan_card"
    AADHAAR_CARD = "aadhaar_card"
    GST_CERTIFICATE = "gst_certificate"
    BANK_STATEMENT = "bank_statement"
    ITR = "itr"
    PROPERTY_DOCUMENT = "property_document"


class ApplicantDocument(BaseModel):
    """A single document submitted by the applicant."""

    document_type: DocumentType
    document_id: str = Field(..., description="Unique identifier for the document")
    content: dict = Field(
        default_factory=dict,
        description="Simulated extracted content from the document",
    )


class LoanApplication(BaseModel):
    """Top-level loan application payload — the input to the system."""

    applicant_id: str = Field(..., description="Unique applicant identifier")
    applicant_name: str = Field(..., description="Full name as provided by applicant")
    pan_number: str = Field(..., description="PAN number (e.g., ABCDE1234F)")
    aadhaar_number: str = Field(..., description="12-digit Aadhaar number")
    date_of_birth: str = Field(..., description="DOB in YYYY-MM-DD format")
    address: str = Field(..., description="Residential address as stated")
    phone_number: str = Field(..., description="10-digit mobile number")
    email: str = Field(default="", description="Email address")
    annual_income: float = Field(..., description="Self-declared annual income in INR")
    loan_amount_requested: float = Field(..., description="Requested loan amount in INR")
    gst_number: str = Field(default="", description="GSTIN if applicable")
    documents: list[ApplicantDocument] = Field(
        default_factory=list,
        description="List of submitted documents",
    )
    remarks: str = Field(default="", description="Free-text remarks or notes")


class ExtractedFields(BaseModel):
    """Fields extracted from documents during the DAG extraction phase.

    These are the 'ground truth' values from documents, which get compared
    against external verification sources.
    """

    applicant_id: str
    name_from_pan: str = ""
    name_from_aadhaar: str = ""
    dob_from_pan: str = ""
    dob_from_aadhaar: str = ""
    address_from_aadhaar: str = ""
    income_from_itr: float = 0.0
    income_from_bank_statement: float = 0.0
    gst_business_name: str = ""
    gst_business_address: str = ""
    pan_number: str = ""
    aadhaar_number: str = ""
    gst_number: str = ""
